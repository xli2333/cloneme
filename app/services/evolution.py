from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..config import settings
from ..db import db
from .gemini_client import get_gemini_client
from .persona import flatten_persona, merge_phrase_scores, normalize_persona_payload

logger = logging.getLogger("doppelganger.evolution")
JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")
PHRASE_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9~～!?！？]{2,16}")


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = JSON_BLOCK_RE.search(text)
    if not match:
        raise ValueError("no json")
    return json.loads(match.group(0))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class EvolutionService:
    def _update_persona_from_samples(self, sample_texts: list[str]) -> int:
        if not sample_texts:
            return 0
        persona_row = db.get_persona_profile()
        if not persona_row:
            return 0

        persona_payload = normalize_persona_payload(persona_row["payload"])
        flat = flatten_persona(persona_payload)
        adaptive = persona_payload.setdefault("adaptive_persona", {})
        speech_traits = adaptive.setdefault("speech_traits", {})
        existing = [str(x) for x in speech_traits.get("top_phrases", []) if str(x).strip()]

        candidate_row = db.get_profile("persona_candidate")
        candidate_payload = candidate_row["payload"] if candidate_row else {"sample_count": 0, "phrase_scores": {}}
        phrase_scores: dict[str, int] = {
            str(k): int(v) for k, v in (candidate_payload.get("phrase_scores", {}) or {}).items()
        }

        for text in sample_texts:
            for item in PHRASE_RE.findall(str(text)):
                token = item.strip()
                if len(token) < 2:
                    continue
                phrase_scores[token] = int(phrase_scores.get(token, 0)) + 1

        sample_count = int(candidate_payload.get("sample_count", 0)) + len(sample_texts)
        db.upsert_profile(
            "persona_candidate",
            {
                "sample_count": sample_count,
                "phrase_scores": phrase_scores,
            },
            bump_version=True,
        )

        if sample_count < int(settings.persona_candidate_min_samples):
            return int(persona_row["version"])

        merged = merge_phrase_scores(
            existing=existing,
            candidate_scores=phrase_scores,
            limit=int(settings.persona_adaptive_top_phrases_limit),
            min_freq=int(settings.persona_candidate_min_phrase_freq),
            forbidden=list(flat.get("relationship", {}).get("forbidden_nicknames", [])),
        )
        speech_traits["top_phrases"] = merged
        adaptive["updated_from_feedback"] = True
        db.upsert_persona_profile(persona_payload, bump_version=True)
        db.upsert_profile("persona_candidate", {"sample_count": 0, "phrase_scores": {}}, bump_version=True)
        latest = db.get_persona_profile()
        return int(latest["version"]) if latest else int(persona_row["version"])

    def summarize_and_update(self, conversation_id: str, message_ids: list[int], comment: str) -> dict[str, Any]:
        with db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, role, content, created_at
                FROM online_conversations
                WHERE conversation_id = ?
                  AND id IN ({','.join('?' for _ in message_ids)})
                ORDER BY id ASC
                """,
                [conversation_id, *message_ids],
            ).fetchall()

        pref_row = db.get_profile("preference")
        if not pref_row:
            raise RuntimeError("preference profile missing")

        if not rows:
            return {
                "accepted_count": 0,
                "preference_version": pref_row["version"],
                "summary": "没有可学习样本",
            }

        sample_texts = [str(r["content"]) for r in rows if str(r["role"]) == "assistant"]
        if not sample_texts:
            return {
                "accepted_count": 0,
                "preference_version": pref_row["version"],
                "summary": "样本中没有虚拟人回复",
            }

        preference = pref_row["payload"]

        prompt = f"""
你是“回复偏好总结器”。请基于用户标注“不错”的回复样本，提炼微调参数。

要求：
1. 不能改变主人格，不允许突破称呼约束（仅 {settings.strict_nickname}）。
2. 只能做小幅度参数微调。
3. 输出 JSON，不要输出解释。

当前偏好配置：{json.dumps(preference, ensure_ascii=False)}
被标注不错的样本：{json.dumps(sample_texts, ensure_ascii=False)}
用户备注：{comment or "无"}

输出 schema：
{{
  "summary": "一句话总结",
  "adjustments": {{
    "laugh_ratio_target_delta": -0.1~0.1,
    "tilde_ratio_target_delta": -0.1~0.1,
    "question_ratio_target_delta": -0.1~0.1,
    "default_bubble_count_delta": -1~1,
    "online_memory_weight_delta": -0.1~0.1
  }}
}}
""".strip()

        try:
            client = get_gemini_client()
            result = client.generate(
                primary_model=settings.gemini_pro_model,
                prompt=prompt,
                temperature=0.15,
                max_output_tokens=700,
                response_mime_type="application/json",
            )
            payload = _extract_json(result.text)
            logger.info("evolution_model_used=%s", result.model_used)
        except Exception as exc:
            logger.warning("evolution_generate_failed fallback_heuristic=true error=%s", exc)
            merged = "".join(sample_texts)
            payload = {
                "summary": "已按最近正反馈样本做保守微调",
                "adjustments": {
                    "laugh_ratio_target_delta": 0.02 if ("哈" in merged) else 0.0,
                    "tilde_ratio_target_delta": 0.01 if ("~" in merged or "～" in merged) else 0.0,
                    "question_ratio_target_delta": 0.0,
                    "default_bubble_count_delta": 0.0,
                    "online_memory_weight_delta": 0.03,
                },
            }

        adjustments = payload.get("adjustments", {})
        tone = preference.setdefault("tone", {})
        multi = preference.setdefault("multi_bubble", {})
        weights = preference.setdefault("weights", {})

        tone["laugh_ratio_target"] = round(
            _clamp(
                float(tone.get("laugh_ratio_target", 0.1))
                + float(adjustments.get("laugh_ratio_target_delta", 0.0)),
                0.0,
                1.0,
            ),
            4,
        )
        tone["tilde_ratio_target"] = round(
            _clamp(
                float(tone.get("tilde_ratio_target", 0.03))
                + float(adjustments.get("tilde_ratio_target_delta", 0.0)),
                0.0,
                1.0,
            ),
            4,
        )
        tone["question_ratio_target"] = round(
            _clamp(
                float(tone.get("question_ratio_target", 0.01))
                + float(adjustments.get("question_ratio_target_delta", 0.0)),
                0.0,
                1.0,
            ),
            4,
        )

        multi["default_count"] = int(
            _clamp(
                float(multi.get("default_count", 2))
                + float(adjustments.get("default_bubble_count_delta", 0.0)),
                1.0,
                4.0,
            )
        )

        weights["online_memory"] = round(
            _clamp(
                float(weights.get("online_memory", 0.13))
                + float(adjustments.get("online_memory_weight_delta", 0.0)),
                0.05,
                0.5,
            ),
            4,
        )

        rest_keys = [k for k in weights.keys() if k != "online_memory"]
        rest_sum = sum(float(weights[k]) for k in rest_keys)
        target_rest = max(0.0, 1.0 - float(weights["online_memory"]))
        if rest_sum > 0:
            scale = target_rest / rest_sum
            for key in rest_keys:
                weights[key] = round(float(weights[key]) * scale, 4)

        preference["nickname"] = {
            "strict_only": settings.strict_nickname,
            "forbidden": settings.forbidden_nicknames,
        }
        preference.setdefault("master_persona", {})
        preference["master_persona"]["locked"] = True

        db.upsert_profile("preference", preference, bump_version=True)
        persona_version = self._update_persona_from_samples(sample_texts)
        latest = db.get_profile("preference")
        return {
            "accepted_count": len(sample_texts),
            "preference_version": latest["version"] if latest else pref_row["version"],
            "persona_version": int(persona_version),
            "summary": str(payload.get("summary") or "已根据反馈微调偏好参数"),
        }


evolution_service = EvolutionService()
