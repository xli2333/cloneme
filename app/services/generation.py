from __future__ import annotations

import json
import logging
import math
import random
import re
import time
from dataclasses import dataclass
from typing import Any

from ..config import settings
from ..db import db
from .gemini_client import get_gemini_client
from .persona import flatten_persona, normalize_persona_payload, persona_brief
from .retrieval import retrieval_service

logger = logging.getLogger("doppelganger.generation")

JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}|\[[\s\S]*\]")
KEYWORD_RE = re.compile(r"[\u4e00-\u9fff]{2,8}|[A-Za-z]{3,24}|\d+")
STOPWORDS = {
    "这个",
    "那个",
    "今天",
    "就是",
    "然后",
    "可以",
    "我们",
    "你们",
    "我的",
    "你的",
    "一下",
}
QUESTION_HINTS = ("吗", "么", "怎么", "为什么", "咋", "是否", "要不要", "?")
META_ARTIFACT_RE = re.compile(r"json|schema|markdown|作为ai|我作为|提示词|system prompt", flags=re.IGNORECASE)
ACTIVITY_QUERY_RE = re.compile(r"(在干嘛|干嘛呢|做什么|忙什么|忙啥|在忙啥|在忙什么)")
STATUS_REPLY_RE = re.compile(r"(我在|在.*呢|刚.*完|准备.*呢|在.*中|还在.*)")
STATUS_UPDATE_RE = re.compile(r"(我在|我刚|我现在|我还在|我正|刚刚|准备|正在)")
FOLLOWUP_RE = re.compile(r"(吗|呢|咋样|怎么样|要不要|想不想|要不|是不是|辣不辣|好吃吗|然后呢|你呢)")
FORBIDDEN_WORD_RE = (
    re.compile("|".join(re.escape(x) for x in settings.forbidden_nicknames))
    if settings.forbidden_nicknames
    else None
)


def _clip(text: str) -> str:
    if len(text) <= settings.log_max_chars:
        return text
    return text[: settings.log_max_chars] + f"...(truncated {len(text) - settings.log_max_chars} chars)"


def _extract_json(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch not in "[{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
            return obj
        except Exception:
            continue

    matches = JSON_BLOCK_RE.findall(text)
    for block in matches:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue

    raise ValueError("no valid json found")


def _coerce_candidates_from_text(text: str) -> list[dict[str, Any]]:
    plain = text.replace("```json", "").replace("```", "").strip()
    lines = [x.strip() for x in plain.splitlines() if x.strip()]
    bubbles: list[str] = []
    for line in lines:
        line = re.sub(r"^[\-\*\d\.\)\(\s]+", "", line).strip()
        if not line:
            continue
        if len(line) > 44:
            line = line[:44].rstrip("。！？!?，,") + "…"
        bubbles.append(line)
        if len(bubbles) >= 3:
            break

    if not bubbles:
        bubbles = [plain[:24].strip() or "我在"]

    return [{"bubbles": bubbles, "strategy": "text_coerce"}]


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


def _keyword_tokens(text: str) -> list[str]:
    base = [t.lower() for t in KEYWORD_RE.findall(text)]
    merged = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text.lower())
    chars = [c for c in merged if "\u4e00" <= c <= "\u9fff"]
    grams: list[str] = []
    if chars:
        for n in (2, 3):
            for i in range(0, max(0, len(chars) - n + 1)):
                grams.append("".join(chars[i : i + n]))
    return [t for t in (base + grams) if t and t not in STOPWORDS]


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 0:
        return vec
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _sanitize_bubble(text: str) -> str:
    result = str(text).strip()
    if not result:
        return ""
    result = result.replace("\u00a0", " ")
    if FORBIDDEN_WORD_RE:
        result = FORBIDDEN_WORD_RE.sub("", result)
    result = re.sub(r"\s+", " ", result).strip()
    result = re.sub(r"([。！？!?~～，,]){2,}", r"\1", result)
    if len(result) > 44:
        result = result[:44].rstrip("。！？!?，,") + "…"
    return result


@dataclass(slots=True)
class GenerationResult:
    bubbles: list[str]
    candidates: list[dict[str, Any]]
    selected_index: int
    planner_model: str
    generator_model: str
    critic_model: str | None
    debug: dict[str, Any]


class GenerationService:
    def __init__(self) -> None:
        self.rng = random.Random()
        self._persona_cache_payload: dict[str, Any] | None = None
        self._persona_cache_at: float = 0.0
        self._persona_cache_version: int = 0

    def _get_persona_cached(self) -> dict[str, Any]:
        ttl = max(5, int(settings.persona_cache_ttl_sec))
        now = time.monotonic()
        if self._persona_cache_payload is not None and (now - self._persona_cache_at) < ttl:
            return self._persona_cache_payload

        row = db.get_persona_profile()
        payload = normalize_persona_payload(row["payload"] if row else {})
        self._persona_cache_payload = payload
        self._persona_cache_at = now
        self._persona_cache_version = int(row["version"]) if row else 0
        return payload

    def _load_profiles(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        style_row = db.get_profile("style")
        pref_row = db.get_profile("preference")
        if not style_row or not pref_row:
            raise RuntimeError("style/preference profiles not found. bootstrap required.")
        persona_payload = self._get_persona_cached()
        return style_row["payload"], pref_row["payload"], persona_payload

    def _build_context_frame(
        self,
        user_message: str,
        recent_block: list[dict[str, Any]],
    ) -> dict[str, Any]:
        recent_n = max(2, settings.context_frame_recent_messages)
        recent_tail = recent_block[-recent_n:]
        user_lines = [str(x.get("content", "")).strip() for x in recent_tail if x.get("role") == "user"]
        assistant_lines = [str(x.get("content", "")).strip() for x in recent_tail if x.get("role") == "assistant"]
        anchors = _keyword_tokens(user_message)
        if user_lines:
            anchors.extend(_keyword_tokens(user_lines[-1]))
        if assistant_lines:
            anchors.extend(_keyword_tokens(assistant_lines[-1]))
        seen: set[str] = set()
        focus_terms: list[str] = []
        for token in anchors:
            if token in seen:
                continue
            seen.add(token)
            focus_terms.append(token)
            if len(focus_terms) >= 14:
                break
        question_like = any(x in user_message for x in QUESTION_HINTS)
        status_update = bool(STATUS_UPDATE_RE.search(user_message)) and not question_like
        assistant_run = 0
        found_user_tail = False
        for row in reversed(recent_block):
            role = str(row.get("role", ""))
            if role == "user" and not found_user_tail:
                found_user_tail = True
                continue
            if role == "assistant":
                assistant_run += 1
                continue
            if assistant_run > 0:
                break

        if status_update:
            bubble_min, bubble_target, bubble_max = 2, 3, 6
        elif question_like:
            bubble_min, bubble_target, bubble_max = 1, 2, 4
        else:
            bubble_min, bubble_target, bubble_max = 1, 2, 5
        if assistant_run >= 2:
            bubble_target = min(6, bubble_target + 1)
            bubble_max = min(8, bubble_max + 1)

        return {
            "focus_terms": focus_terms,
            "last_user": user_lines[-1] if user_lines else "",
            "last_assistant": assistant_lines[-1] if assistant_lines else "",
            "question_like": question_like,
            "status_update": status_update,
            "assistant_run": assistant_run,
            "bubble_hint": {
                "min": bubble_min,
                "target": bubble_target,
                "max": bubble_max,
            },
        }

    def _build_context_block(
        self,
        conversation_id: str,
        user_message: str,
        persona: dict[str, Any],
    ) -> dict[str, Any]:
        recent = retrieval_service.get_recent_messages(conversation_id, limit=24)
        online_memory = retrieval_service.retrieve_online_memory(conversation_id, user_message, k=12)
        segments = retrieval_service.retrieve_similar_segments(
            user_message,
            top_k_hits=settings.semantic_top_segments,
            window_before=settings.segment_window_before,
            window_after=settings.segment_window_after,
        )

        recent_block = [{"id": r["id"], "role": r["role"], "content": r["content"]} for r in recent[-12:]]
        online_block = [{"role": r["role"], "content": r["content"]} for r in online_memory[:10]]
        style_block: list[str] = []
        for seg in segments[:4]:
            for line in seg.get("lines", []):
                if line.get("role") == "assistant" and str(line.get("content", "")).strip():
                    style_block.append(str(line.get("content")))
                if len(style_block) >= 18:
                    break
            if len(style_block) >= 18:
                break

        if len(style_block) < 10:
            style_refs = retrieval_service.retrieve_baseline_style(user_message, k=settings.retrieval_top_k)
            style_block.extend([r["content"] for r in style_refs[: max(0, 18 - len(style_block))]])
            style_block = style_block[:18]

        frame = self._build_context_frame(user_message, recent_block)
        rag_chars = sum(
            len(str(ln.get("content", "")))
            for seg in segments
            for ln in seg.get("lines", [])
            if str(ln.get("content", "")).strip()
        )

        logger.info(
            "rag_context conversation=%s recent=%d online=%d style_refs=%d segments=%d rag_chars=%d",
            conversation_id,
            len(recent_block),
            len(online_block),
            len(style_block),
            len(segments),
            rag_chars,
        )

        if segments:
            top = segments[0]
            logger.info(
                "rag_best_segment segment_id=%s retrieval=%.4f semantic=%.4f lexical=%.4f anchor=%s",
                top.get("segment_id"),
                float(top.get("retrieval_score", 0.0)),
                float(top.get("semantic_score", 0.0)),
                float(top.get("lexical_score", 0.0)),
                _clip(str(top.get("anchor_text", ""))),
            )
            if settings.log_raw_model_output:
                raw_lines = "\n".join([f"{x.get('role')}: {x.get('content')}" for x in top.get("lines", [])])
                logger.info("rag_best_segment_lines\n%s", _clip(raw_lines))

        return {
            "recent_block": recent_block,
            "online_block": online_block,
            "style_block": style_block,
            "segments": segments,
            "frame": frame,
            "persona": persona_brief(persona, phrase_limit=14),
            "rag_chars": rag_chars,
        }

    def _plan_prompt(
        self,
        user_message: str,
        style: dict[str, Any],
        preference: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        segments = context.get("segments", [])[:3]
        frame = context.get("frame", {})
        persona = context.get("persona", {})
        return f"""
你是“Doppelganger对话规划器”。目标：不偏题，并且保持目标人物语气。

优先级：
1. 先承接当前用户语境，不跑题。
2. 再用历史原文学习表达习惯。
3. 最后保持长期人格一致。

硬约束：
1. 亲昵称呼只能使用“{settings.strict_nickname}”，禁止其他称呼。
2. 输出必须是 JSON，不要输出解释。

用户当前消息：{user_message}
短期语境框架：{json.dumps(frame, ensure_ascii=False)}
风格统计：{json.dumps(style, ensure_ascii=False)}
偏好配置：{json.dumps(preference, ensure_ascii=False)}
最近对话：{json.dumps(context['recent_block'], ensure_ascii=False)}
在线记忆：{json.dumps(context['online_block'], ensure_ascii=False)}
历史相似片段：{json.dumps(segments, ensure_ascii=False)}
长期人格：{json.dumps(persona, ensure_ascii=False)}

请输出 JSON:
{{
  "candidate_count": 10-20,
  "bubble_count": 1-8,
  "length_targets": [每条目标字数],
  "tone_tags": ["确认","安抚","轻松","追问"中的若干],
  "should_use_nickname": true/false,
  "rationale": "不超过40字"
}}
""".strip()

    def _generation_prompt(
        self,
        user_message: str,
        plan: dict[str, Any],
        context: dict[str, Any],
        candidate_count: int,
    ) -> str:
        segments = context.get("segments", [])[:3]
        frame = context.get("frame", {})
        persona = context.get("persona", {})
        return f"""
你就是目标人物本人在聊天。请根据历史原文学习表达，并优先承接当前语境。

规则：
1. 不偏题：必须回应用户当前这句话，不要跳到无关话题。
2. 语义优先：先把当前问题接住，再补充情绪和语气。
3. RAG原文用于学习表达和语义关联，不要照抄整句。
4. 亲昵称呼只能是“{settings.strict_nickname}”。
5. 禁止输出 JSON 说明、模型解释、客服腔、教程腔。
6. 输出严格 JSON，不要 markdown。
7. 你的回复必须能把对话继续下去，避免只复述用户原话。

用户当前消息：{user_message}
短期语境框架：{json.dumps(frame, ensure_ascii=False)}
规划：{json.dumps(plan, ensure_ascii=False)}
最近对话：{json.dumps(context['recent_block'], ensure_ascii=False)}
在线记忆：{json.dumps(context['online_block'], ensure_ascii=False)}
历史相似片段原文：{json.dumps(segments, ensure_ascii=False)}
长期人格：{json.dumps(persona, ensure_ascii=False)}

请生成 {candidate_count} 组候选，每组 1-8 条气泡（按短期语境决定，可一条也可多条连发）：
{{
  "candidates": [
    {{"bubbles": ["文本1","文本2"], "strategy": "8字内策略说明"}}
  ]
}}
""".strip()

    def _critic_prompt(self, user_message: str, candidates: list[dict[str, Any]]) -> str:
        compact = [
            {
                "idx": i,
                "bubbles": c.get("bubbles", []),
                "offtopic": round(float(c.get("offtopic_score", 0.0)), 3),
                "persona": round(float(c.get("persona_score", 0.0)), 3),
            }
            for i, c in enumerate(candidates)
        ]
        return f"""
你是风格复核器。目标：选出最承接当前语境且保持同一人格的候选。

用户当前消息：{user_message}
候选：{json.dumps(compact, ensure_ascii=False)}

输出 JSON:
{{
  "winner_index": 整数,
  "reason": "不超过40字"
}}
""".strip()

    def _repair_prompt(
        self,
        user_message: str,
        frame: dict[str, Any],
        persona: dict[str, Any],
        bubbles: list[str],
    ) -> str:
        return f"""
请做“最小改写修复”。目标：保持原语气和句式，只修复偏题或断聊部分，让回复贴合当前语境并能继续聊下去。

要求：
1. 只改必要的词句，不要整段重写。
2. 回复里至少给一个可接续点（追问、确认、补充）。
3. 亲昵称呼只能使用“{settings.strict_nickname}”。
4. 输出 JSON，不要解释。

用户当前消息：{user_message}
短期语境框架：{json.dumps(frame, ensure_ascii=False)}
长期人格：{json.dumps(persona, ensure_ascii=False)}
原候选：{json.dumps(bubbles, ensure_ascii=False)}

输出：
{{
  "bubbles": ["修复后文本1","修复后文本2"],
  "reason": "不超过20字"
}}
""".strip()

    def _hard_filter(self, bubbles: list[str]) -> tuple[bool, str]:
        if not bubbles:
            return False, "empty"
        if any(not b.strip() for b in bubbles):
            return False, "blank"
        if any(b.strip() in {"选中", "不错", "提交", "发送", "标记"} for b in bubbles):
            return False, "ui_artifact"
        if any(META_ARTIFACT_RE.search(b) for b in bubbles):
            return False, "meta_artifact"
        if FORBIDDEN_WORD_RE and any(FORBIDDEN_WORD_RE.search(b) for b in bubbles):
            return False, "forbidden_nickname"
        if any(len(b) > 50 for b in bubbles):
            return False, "too_long"
        if all(not re.search(r"[\u4e00-\u9fff]", b) for b in bubbles):
            return False, "non_chinese"
        return True, "ok"

    def _semantic_relevance_scores(self, user_message: str, candidate_texts: list[str], client) -> list[float]:
        if not candidate_texts:
            return []
        try:
            q = client.embed_texts(
                [user_message],
                model=settings.gemini_embedding_model,
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=settings.gemini_embedding_dim,
            )[0]
            docs = client.embed_texts(
                candidate_texts,
                model=settings.gemini_embedding_model,
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=settings.gemini_embedding_dim,
            )
            qn = _normalize(q)
            scores: list[float] = []
            for d in docs:
                s = _cosine(qn, _normalize(d))
                scores.append(float(_clamp(s, 0.0, 1.0)))
            return scores
        except Exception as exc:
            logger.warning("candidate_semantic_relevance_failed error=%s", exc)
            return [self._relevance_score(user_message, [x]) for x in candidate_texts]

    def _relevance_score(self, user_message: str, bubbles: list[str]) -> float:
        tokens = set(_keyword_tokens(user_message))
        if not tokens:
            return 0.5
        text = "".join(bubbles).lower()
        hit = sum(1 for t in tokens if t in text)
        return float(_clamp(hit / max(1, len(tokens)), 0.0, 1.0))

    def _style_score(
        self,
        bubbles: list[str],
        style: dict[str, Any],
        preference: dict[str, Any],
        frame: dict[str, Any] | None = None,
    ) -> float:
        if not bubbles:
            return 0.0
        lengths = [len(x) for x in bubbles]
        avg_len = sum(lengths) / len(lengths)
        target_len = float(style.get("avg_len", 6.0))
        len_score = 1.0 - min(abs(avg_len - target_len) / max(1.0, target_len), 1.0)

        short_ratio = sum(1 for x in lengths if x <= 10) / max(1, len(lengths))
        hint = (frame or {}).get("bubble_hint", {})
        bubble_target = float(hint.get("target", preference.get("multi_bubble", {}).get("default_count", 2.0)))
        bubble_min = float(hint.get("min", 1))
        bubble_max = float(hint.get("max", 6))
        n = float(len(bubbles))
        if n < bubble_min:
            bubble_score = max(0.0, 1.0 - (bubble_min - n) / max(1.0, bubble_min))
        elif n > bubble_max:
            bubble_score = max(0.0, 1.0 - (n - bubble_max) / max(1.0, bubble_max))
        else:
            bubble_score = 1.0 - min(abs(n - bubble_target) / max(2.0, bubble_target), 1.0)

        text = "".join(bubbles)
        laugh_target = float(preference.get("tone", {}).get("laugh_ratio_target", 0.1))
        laugh_here = 1.0 if re.search(r"(哈哈|笑死|hhh)", text, flags=re.IGNORECASE) else 0.0
        laugh_score = 1.0 - abs(laugh_here - laugh_target)

        return float(_clamp(0.42 * len_score + 0.26 * short_ratio + 0.22 * bubble_score + 0.10 * laugh_score, 0.0, 1.0))

    def _context_score(self, bubbles: list[str], context: dict[str, Any]) -> float:
        online = context.get("online_block", [])
        if not online:
            return 0.55
        text = "".join(bubbles)
        hit = 0
        for row in online[:8]:
            ref = str(row.get("content", "")).strip()
            if not ref:
                continue
            key = ref[:6]
            if key and key in text:
                hit += 1
        return float(_clamp(0.30 + hit * 0.12, 0.0, 1.0))

    def _conversation_flow_score(self, user_message: str, bubbles: list[str], frame: dict[str, Any]) -> float:
        if not bubbles:
            return 0.0
        text = "".join(bubbles)
        question_like = bool(frame.get("question_like"))
        status_update = bool(frame.get("status_update"))
        has_followup = bool(FOLLOWUP_RE.search(text))
        has_status = bool(STATUS_REPLY_RE.search(text))
        flow = 0.35

        if question_like:
            flow += 0.28 if has_status or re.search(r"(可以|不行|能|要|是|不是|会|不会|先|再)", text) else 0.06
            flow += 0.16 if has_followup else 0.0
        elif status_update:
            flow += 0.26 if has_status else 0.08
            flow += 0.22 if has_followup else 0.04
        else:
            flow += 0.14 if has_status else 0.05
            flow += 0.14 if has_followup else 0.05

        if len(bubbles) >= 3:
            flow += 0.07
        elif len(bubbles) == 1 and len(text) <= 5:
            flow -= 0.14

        # Laugh tokens are persona-positive emotional signals and should not be punished.
        # We only penalize mechanical keyword echo loops below.
        if re.search(r"(火鸡面|你在干嘛|干嘛呢|好吃吗)(?:\1)+", text):
            flow -= 0.28
        return float(_clamp(flow, 0.0, 1.0))

    def _echo_penalty(self, user_message: str, bubbles: list[str]) -> float:
        user_tokens = set(_keyword_tokens(user_message))
        if not user_tokens:
            return 0.0
        cand_tokens = set(_keyword_tokens("".join(bubbles)))
        if not cand_tokens:
            return 0.0
        overlap = len(user_tokens & cand_tokens) / max(1, len(cand_tokens))
        new_ratio = len(cand_tokens - user_tokens) / max(1, len(cand_tokens))
        penalty = 0.0
        if overlap >= 0.78 and new_ratio <= 0.22:
            penalty += 0.18
        joined = "".join(bubbles)
        if len(joined) <= 12 and len(cand_tokens) <= 3 and overlap >= 0.6:
            penalty += 0.10
        if re.search(r"(火鸡面|你在干嘛|干嘛呢|好吃吗)(?:\1)+", joined):
            penalty += 0.22
        # Do not penalize repeated laugh expressions; keep persona expressiveness.
        if re.search(r"(哈哈|h{2,}|呵呵|嘿嘿)+", joined, flags=re.IGNORECASE):
            return float(_clamp(penalty, 0.0, 0.35))
        if re.search(r"(.{2,8})\1", joined):
            penalty += 0.08
        return float(_clamp(penalty, 0.0, 0.35))

    def _segment_alignment_score(self, bubbles: list[str], context: dict[str, Any]) -> float:
        segments = context.get("segments", [])
        if not segments:
            return 0.5
        top = segments[0]
        refs = [
            str(x.get("content", "")).strip()
            for x in top.get("lines", [])
            if str(x.get("role", "")) == "assistant" and str(x.get("content", "")).strip()
        ]
        if not refs:
            return 0.5

        ref_text = "".join(refs)
        cand_text = "".join(bubbles)

        ref_tokens = set(_keyword_tokens(ref_text))
        cand_tokens = set(_keyword_tokens(cand_text))
        overlap = len(ref_tokens & cand_tokens) / max(1, len(cand_tokens)) if cand_tokens else 0.0

        ref_avg = sum(len(x) for x in refs) / len(refs)
        cand_avg = sum(len(x) for x in bubbles) / len(bubbles)
        len_score = 1.0 - min(abs(cand_avg - ref_avg) / max(1.0, ref_avg), 1.0)

        p_ref = bool(re.search(r"[!?！？~～]", ref_text))
        p_cand = bool(re.search(r"[!?！？~～]", cand_text))
        p_score = 1.0 if p_ref == p_cand else 0.0

        return float(_clamp(0.55 * overlap + 0.35 * len_score + 0.10 * p_score, 0.0, 1.0))

    def _copy_penalty(self, bubbles: list[str], context: dict[str, Any]) -> float:
        segments = context.get("segments", [])
        if not segments:
            return 0.0
        ref_set = {
            str(x.get("content", "")).strip()
            for seg in segments[:2]
            for x in seg.get("lines", [])
            if str(x.get("role", "")) == "assistant" and str(x.get("content", "")).strip()
        }
        penalty = 0.0
        for b in bubbles:
            t = b.strip()
            if not t:
                continue
            if t in ref_set and len(t) >= 10:
                penalty += 0.08
        return min(0.22, penalty)

    def _persona_consistency_score(self, bubbles: list[str], persona: dict[str, Any]) -> float:
        if not settings.enable_persona_guard:
            return 0.7
        if not bubbles:
            return 0.0
        flat = flatten_persona(persona)
        text = "".join(bubbles)
        score = 0.65

        forbidden = flat.get("relationship", {}).get("forbidden_nicknames", settings.forbidden_nicknames)
        if forbidden:
            pat = re.compile("|".join(re.escape(x) for x in forbidden))
            if pat.search(text):
                return 0.0

        traits = flat.get("speech_traits", {})
        target_len = float(traits.get("avg_len", 8.0))
        avg_len = sum(len(x) for x in bubbles) / max(1, len(bubbles))
        len_align = 1.0 - min(abs(avg_len - target_len) / max(1.0, target_len), 1.0)
        score += 0.2 * len_align

        phrases = [str(x) for x in traits.get("top_phrases", [])[:30] if str(x).strip()]
        if phrases:
            hit = sum(1 for p in phrases if p in text)
            score += 0.15 * _clamp(hit / 4.0, 0.0, 1.0)
        else:
            score += 0.08

        return float(_clamp(score, 0.0, 1.0))

    def _offtopic_score(
        self,
        user_message: str,
        bubbles: list[str],
        frame: dict[str, Any],
        *,
        relevance_hint: float | None = None,
    ) -> float:
        if not settings.enable_offtopic_penalty:
            return 0.0
        if not bubbles:
            return 1.0
        text = "".join(bubbles)
        text_tokens = set(_keyword_tokens(text))
        anchors = list(frame.get("focus_terms", []))
        if not anchors:
            anchors = _keyword_tokens(user_message)
        anchors = anchors[:12]
        if not anchors:
            return 0.25

        hit = sum(1 for t in anchors if t in text_tokens or t in text)
        coverage = hit / max(1, len(anchors))
        # Keep this as a soft penalty instead of hard rejection.
        drift = (1.0 - coverage) * 0.75

        ask_like = bool(frame.get("question_like"))
        if ask_like and not re.search(r"[?？]|(是|要|可以|行|能|不行|怎么|因为|所以)", text):
            drift += 0.08

        # Intent compatibility: "你在干嘛" 类问题，回复当前状态应视为同题。
        if ACTIVITY_QUERY_RE.search(user_message) and STATUS_REPLY_RE.search(text):
            drift -= 0.28

        # High semantic relevance should reduce drift penalties.
        if relevance_hint is not None:
            drift -= 0.30 * float(_clamp(relevance_hint, 0.0, 1.0))

        if re.search(r"(不过|更想聊|先不聊|换个话题|另外聊|题外话|扯远了)", text):
            drift += 0.18
        extras = [t for t in text_tokens if t not in set(anchors) and len(t) >= 2]
        if coverage < 0.45 and len(extras) >= 3:
            drift += min(0.14, 0.02 * len(extras))
        if META_ARTIFACT_RE.search(text):
            drift += 0.22
        return float(_clamp(drift, 0.0, 1.0))

    def _weighted_total(
        self,
        rel: float,
        style_s: float,
        flow_s: float,
        seg_s: float,
        ctx_s: float,
        persona_s: float,
        copy_pen: float,
        echo_pen: float,
        offtopic: float,
        preference: dict[str, Any],
    ) -> float:
        weights = preference.get("weights", {})
        w_sem = float(weights.get("semantic", 0.45))
        w_style = float(weights.get("style", 0.22))
        w_relation = float(weights.get("relation", 0.12))
        w_recency = float(weights.get("recency", 0.08))
        w_online = float(weights.get("online_memory", 0.13))
        base = (
            w_sem * rel
            + w_style * style_s
            + w_relation * persona_s
            + w_recency * seg_s
            + w_online * ctx_s
            + 0.24 * flow_s
        )
        pen = copy_pen + echo_pen + settings.offtopic_penalty_weight * offtopic + 0.12 * max(0.0, 0.46 - flow_s)
        if settings.enable_persona_guard:
            pen += settings.persona_guard_penalty_weight * max(0.0, 0.55 - persona_s)
        return float(_clamp(base - pen, 0.0, 1.0))

    def _score_candidate(
        self,
        user_message: str,
        bubbles: list[str],
        context: dict[str, Any],
        style: dict[str, Any],
        preference: dict[str, Any],
        persona: dict[str, Any],
        rel_hint: float | None = None,
    ) -> dict[str, Any]:
        rel = rel_hint if rel_hint is not None else self._relevance_score(user_message, bubbles)
        frame = context.get("frame", {})
        style_s = self._style_score(bubbles, style, preference, frame=frame)
        flow_s = self._conversation_flow_score(user_message, bubbles, frame)
        seg_s = self._segment_alignment_score(bubbles, context)
        ctx_s = self._context_score(bubbles, context)
        persona_s = self._persona_consistency_score(bubbles, persona)
        offtopic = self._offtopic_score(
            user_message,
            bubbles,
            frame,
            relevance_hint=rel,
        )
        copy_pen = self._copy_penalty(bubbles, context)
        echo_pen = self._echo_penalty(user_message, bubbles)
        total = self._weighted_total(
            rel,
            style_s,
            flow_s,
            seg_s,
            ctx_s,
            persona_s,
            copy_pen,
            echo_pen,
            offtopic,
            preference,
        )
        return {
            "relevance_score": rel,
            "style_score": style_s,
            "flow_score": flow_s,
            "segment_score": seg_s,
            "context_score": ctx_s,
            "persona_score": persona_s,
            "offtopic_score": offtopic,
            "copy_penalty": copy_pen,
            "echo_penalty": echo_pen,
            "total_score": total,
        }

    def _repair_candidate(
        self,
        *,
        user_message: str,
        context: dict[str, Any],
        bubbles: list[str],
        client: Any,
    ) -> tuple[list[str], str] | None:
        if not settings.enable_repair_pass:
            return None
        try:
            repair_result = client.generate(
                primary_model=settings.gemini_pro_model,
                prompt=self._repair_prompt(
                    user_message=user_message,
                    frame=context.get("frame", {}),
                    persona=context.get("persona", {}),
                    bubbles=bubbles,
                ),
                temperature=0.15,
                max_output_tokens=420,
                response_mime_type="application/json",
            )
            if settings.log_raw_model_output:
                logger.info("repair_raw_output\n%s", _clip(repair_result.text))
            payload = _extract_json(repair_result.text)
            if isinstance(payload, dict):
                vals = payload.get("bubbles", [])
                reason = str(payload.get("reason") or "repair")
            else:
                vals = []
                reason = "repair_invalid_json"
            repaired = [_sanitize_bubble(x) for x in vals]
            repaired = [x for x in repaired if x]
            ok, _ = self._hard_filter(repaired)
            if not ok:
                return None
            return repaired, reason
        except Exception as exc:
            logger.warning("repair_failed error=%s", exc)
            return None

    def _fallback_lines(self, user_message: str, frame: dict[str, Any], persona: dict[str, Any]) -> list[str]:
        snippet = user_message.strip().replace("\n", " ")
        if len(snippet) > settings.context_frame_anchor_chars:
            snippet = snippet[: settings.context_frame_anchor_chars].rstrip() + "…"
        flat = flatten_persona(persona)
        nickname = (
            flat.get("relationship", {}).get("strict_nickname")
            or settings.strict_nickname
        )
        first = _sanitize_bubble(f"{nickname}，我在，先接住你这个点。")
        second = _sanitize_bubble(f"你刚刚说的是「{snippet}」，我按这个继续。")
        lines = [x for x in [first, second] if x]
        return lines[:2] or ["我在", "你继续说，我接得住"]

    def _compute_delays(self, bubbles: list[str], base_ms: int = 500) -> list[int]:
        out: list[int] = []
        total = 0
        for text in bubbles:
            typing_ms = base_ms + min(len(text), 26) * self.rng.randint(45, 88)
            total += typing_ms
            out.append(total)
        return out

    def generate(self, conversation_id: str, user_message: str) -> GenerationResult:
        logger.info("chat_generate_start conversation=%s user=%s", conversation_id, _clip(user_message))
        style, preference, persona = self._load_profiles()
        context = self._build_context_block(conversation_id, user_message, persona)
        client = get_gemini_client()

        planner_result = client.generate(
            primary_model=settings.gemini_pro_model,
            prompt=self._plan_prompt(user_message, style, preference, context),
            temperature=0.25,
            max_output_tokens=900,
            response_mime_type="application/json",
        )
        logger.info("planner_model_used=%s", planner_result.model_used)
        if settings.log_raw_model_output:
            logger.info("planner_raw_output\n%s", _clip(planner_result.text))

        try:
            plan_raw = _extract_json(planner_result.text)
            if isinstance(plan_raw, dict):
                plan = plan_raw
            elif isinstance(plan_raw, list) and plan_raw and isinstance(plan_raw[0], dict):
                plan = plan_raw[0]
            else:
                raise ValueError("planner json is not object")
        except Exception:
            bubble_hint = context.get("frame", {}).get("bubble_hint", {})
            plan = {
                "candidate_count": max(10, settings.generation_candidates),
                "bubble_count": int(bubble_hint.get("target", 2)),
                "length_targets": [6, 10],
                "tone_tags": ["确认", "轻松"],
                "should_use_nickname": False,
                "rationale": "fallback_plan",
            }
            logger.warning("planner_parse_failed use_fallback_plan=true")

        candidate_count = _safe_int(plan.get("candidate_count"), settings.generation_candidates)
        candidate_count = int(_clamp(candidate_count, 8, 20))

        generator_result = client.generate(
            primary_model=settings.gemini_flash_model,
            prompt=self._generation_prompt(user_message, plan, context, candidate_count),
            temperature=0.72,
            max_output_tokens=2800,
            response_mime_type="application/json",
        )
        logger.info("generator_model_used=%s", generator_result.model_used)
        if settings.log_raw_model_output:
            logger.info("generator_raw_output\n%s", _clip(generator_result.text))

        try:
            parsed = _extract_json(generator_result.text)
            if isinstance(parsed, dict):
                raw_candidates = parsed.get("candidates", [])
            elif isinstance(parsed, list):
                raw_candidates = parsed
            else:
                raw_candidates = []
            if not isinstance(raw_candidates, list):
                raw_candidates = []
        except Exception:
            raw_candidates = _coerce_candidates_from_text(generator_result.text)
            logger.warning("generator_parse_failed use_text_coerce=true")

        prelim: list[dict[str, Any]] = []
        for item in raw_candidates:
            bubbles = [_sanitize_bubble(x) for x in item.get("bubbles", [])]
            bubbles = [x for x in bubbles if x]
            ok, reason = self._hard_filter(bubbles)
            if not ok:
                continue
            prelim.append({"bubbles": bubbles, "strategy": str(item.get("strategy") or ""), "filter_reason": reason})

        semantic_scores = self._semantic_relevance_scores(
            user_message,
            [" ".join(x["bubbles"]) for x in prelim],
            client,
        )

        scored: list[dict[str, Any]] = []
        for idx, item in enumerate(prelim):
            bubbles = item["bubbles"]
            rel_hint = semantic_scores[idx] if idx < len(semantic_scores) else None
            metrics = self._score_candidate(
                user_message=user_message,
                bubbles=bubbles,
                context=context,
                style=style,
                preference=preference,
                persona=persona,
                rel_hint=rel_hint,
            )
            if float(metrics["relevance_score"]) < 0.05:
                continue
            scored.append(
                {
                    "bubbles": bubbles,
                    "strategy": item.get("strategy", ""),
                    **metrics,
                }
            )

        final_path = "direct"
        fallback_reason = ""
        repair_applied = False

        if not scored:
            logger.warning("candidate_pool_empty trigger_fallback=true")
            fallback_lines = self._fallback_lines(user_message, context.get("frame", {}), persona)
            fallback_metrics = self._score_candidate(
                user_message=user_message,
                bubbles=fallback_lines,
                context=context,
                style=style,
                preference=preference,
                persona=persona,
                rel_hint=0.58,
            )
            scored = [{"bubbles": fallback_lines, "strategy": "fallback_persona", **fallback_metrics}]
            final_path = "fallback"
            fallback_reason = "empty_candidate_pool"

        scored.sort(key=lambda x: x["total_score"], reverse=True)
        logger.info(
            "candidate_scores=%s",
            [
                {
                    "strategy": c.get("strategy"),
                    "rel": round(float(c.get("relevance_score", 0.0)), 4),
                    "style": round(float(c.get("style_score", 0.0)), 4),
                    "flow": round(float(c.get("flow_score", 0.0)), 4),
                    "seg": round(float(c.get("segment_score", 0.0)), 4),
                    "ctx": round(float(c.get("context_score", 0.0)), 4),
                    "persona": round(float(c.get("persona_score", 0.0)), 4),
                    "offtopic": round(float(c.get("offtopic_score", 0.0)), 4),
                    "copy": round(float(c.get("copy_penalty", 0.0)), 4),
                    "echo": round(float(c.get("echo_penalty", 0.0)), 4),
                    "total": round(float(c.get("total_score", 0.0)), 4),
                }
                for c in scored[:8]
            ],
        )

        rerank_pool = scored[: max(1, min(settings.rerank_top_k, len(scored)))]
        selected_index = 0
        critic_model_used: str | None = None

        if len(rerank_pool) > 1:
            try:
                critic_result = client.generate(
                    primary_model=settings.gemini_pro_model,
                    prompt=self._critic_prompt(user_message, rerank_pool),
                    temperature=0.1,
                    max_output_tokens=280,
                    response_mime_type="application/json",
                )
                critic_model_used = critic_result.model_used
                if settings.log_raw_model_output:
                    logger.info("critic_raw_output\n%s", _clip(critic_result.text))
                critic_json = _extract_json(critic_result.text)
                idx = _safe_int(critic_json.get("winner_index"), 0)
                if 0 <= idx < len(rerank_pool):
                    top = rerank_pool[0]
                    choice = rerank_pool[idx]
                    if float(choice["relevance_score"]) >= float(top["relevance_score"]) - 0.04:
                        selected_index = idx
            except Exception:
                logger.warning("critic_parse_failed fallback_to_top=true")
                selected_index = 0

        selected = dict(rerank_pool[selected_index])

        mid = float(settings.repair_threshold_mid)
        high = float(settings.repair_threshold_high)

        if settings.enable_repair_pass and final_path != "fallback":
            offtopic_now = float(selected.get("offtopic_score", 0.0))
            persona_now = float(selected.get("persona_score", 1.0))
            flow_now = float(selected.get("flow_score", 1.0))
            should_repair = (offtopic_now > settings.repair_threshold_low and offtopic_now <= high) or (
                settings.enable_persona_guard and persona_now < settings.persona_guard_repair_threshold
            ) or (flow_now < 0.46)
            if should_repair:
                repaired = self._repair_candidate(
                    user_message=user_message,
                    context=context,
                    bubbles=selected["bubbles"],
                    client=client,
                )
                if repaired:
                    repaired_bubbles, repair_reason = repaired
                    repaired_metrics = self._score_candidate(
                        user_message=user_message,
                        bubbles=repaired_bubbles,
                        context=context,
                        style=style,
                        preference=preference,
                        persona=persona,
                    )
                    better = (
                        float(repaired_metrics["offtopic_score"]) < float(selected["offtopic_score"]) - 0.08
                        or float(repaired_metrics["total_score"]) > float(selected["total_score"]) + 0.03
                    )
                    acceptable = (
                        float(repaired_metrics["offtopic_score"]) <= high
                        and float(repaired_metrics["persona_score"]) >= min(0.3, settings.persona_guard_repair_threshold - 0.2)
                    )
                    if better or acceptable:
                        selected = {
                            **selected,
                            "bubbles": repaired_bubbles,
                            "strategy": f"{selected.get('strategy', '')}|repair",
                            **repaired_metrics,
                        }
                        repair_applied = True
                        final_path = "repair"
                        logger.info("repair_applied reason=%s", repair_reason)

        if final_path != "fallback":
            offtopic_now = float(selected.get("offtopic_score", 0.0))
            persona_now = float(selected.get("persona_score", 1.0))
            flow_now = float(selected.get("flow_score", 1.0))
            too_offtopic = (
                settings.enable_offtopic_penalty
                and offtopic_now > high
                and float(selected.get("relevance_score", 0.0)) < 0.52
                and flow_now < 0.35
            )
            persona_broken = settings.enable_persona_guard and persona_now < max(0.2, settings.persona_guard_repair_threshold - 0.25)
            flow_broken = flow_now < 0.15 and float(selected.get("relevance_score", 0.0)) < 0.45
            if too_offtopic or persona_broken or flow_broken:
                selected["bubbles"] = self._fallback_lines(user_message, context.get("frame", {}), persona)
                selected["strategy"] = "fallback_persona"
                fallback_metrics = self._score_candidate(
                    user_message=user_message,
                    bubbles=selected["bubbles"],
                    context=context,
                    style=style,
                    preference=preference,
                    persona=persona,
                    rel_hint=max(0.45, 1.0 - offtopic_now),
                )
                selected.update(fallback_metrics)
                final_path = "fallback"
                if too_offtopic:
                    fallback_reason = "offtopic_high"
                elif persona_broken:
                    fallback_reason = "persona_low"
                else:
                    fallback_reason = "flow_low"

        if final_path == "repair" and float(selected.get("offtopic_score", 0.0)) <= mid * 0.6:
            logger.info("repair_kept stable_of_topic=%.4f", float(selected.get("offtopic_score", 0.0)))

        delays = self._compute_delays(selected["bubbles"])
        logger.info(
            "chat_generate_done selected_index=%d strategy=%s final_path=%s offtopic=%.4f persona=%.4f",
            selected_index,
            selected.get("strategy", ""),
            final_path,
            float(selected.get("offtopic_score", 0.0)),
            float(selected.get("persona_score", 0.0)),
        )

        return GenerationResult(
            bubbles=selected["bubbles"],
            candidates=rerank_pool,
            selected_index=selected_index,
            planner_model=planner_result.model_used,
            generator_model=generator_result.model_used,
            critic_model=critic_model_used,
            debug={
                "plan": plan,
                "selected_strategy": selected.get("strategy", ""),
                "candidate_count": len(rerank_pool),
                "scores": [c["total_score"] for c in rerank_pool],
                "delays": delays,
                "final_path": final_path,
                "repair_applied": repair_applied,
                "fallback_reason": fallback_reason,
                "offtopic_score": float(selected.get("offtopic_score", 0.0)),
                "persona_score": float(selected.get("persona_score", 0.0)),
                "memory_contribution": {
                    "short": round(float(selected.get("flow_score", 0.0)), 4),
                    "medium": round(float(selected.get("segment_score", 0.0)), 4),
                    "long": round(float(selected.get("persona_score", 0.0)), 4),
                },
                "rag_chars": int(context.get("rag_chars", 0)),
            },
        )


generation_service = GenerationService()
