from __future__ import annotations

import json
import logging
import re
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import settings
from ..db import db, utc_now_iso
from .persona import normalize_persona_payload

logger = logging.getLogger("doppelganger.bootstrap")

GARBLE_RE = re.compile(r"(锟|�|/span>|<span|\\\\x)")
TOKEN_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9~～!?！？。,.，、]+")
QUESTION_RE = re.compile(r"[?？]")
EXCLAIM_RE = re.compile(r"[!！]")
LAUGH_RE = re.compile(r"(哈哈|笑死|hhh)", flags=re.IGNORECASE)
PHRASE_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9~～!?！？]{2,16}")


def parse_timestamp_to_unix(raw: str) -> int | None:
    if not raw:
        return None
    fmts = [
        "%Y-%m-%d %I:%M:%S %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(raw, fmt)
            return int(dt.timestamp())
        except ValueError:
            continue
    return None


def _normalize_role(sender: str, target_sender: str, user_candidates: set[str]) -> str:
    if sender == target_sender:
        return "assistant"
    if sender in user_candidates:
        return "user"
    return "user"


def _extract_tokens(text: str) -> list[str]:
    tokens = TOKEN_RE.findall(text)
    out: list[str] = []
    for token in tokens:
        t = token.strip().lower()
        if not t:
            continue
        if len(t) == 1 and t not in {"嗯", "啊", "哦", "哈"}:
            continue
        out.append(t)
    return out


def _compute_style_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assistant_rows = [r for r in rows if r["role"] == "assistant" and str(r["msg_type"]) == "1"]
    clean_rows = [r for r in assistant_rows if not int(r.get("is_garbled", 0)) and str(r["content"]).strip()]
    lengths = [len(str(r["content"])) for r in clean_rows]
    lengths_sorted = sorted(lengths) if lengths else [0]

    tokens = Counter()
    prefix2 = Counter()
    suffix2 = Counter()

    for row in clean_rows:
        text = str(row["content"]).strip()
        tokens.update(_extract_tokens(text))
        if len(text) >= 2:
            prefix2[text[:2]] += 1
            suffix2[text[-2:]] += 1

    run_lengths: list[int] = []
    cur = 0
    for row in rows:
        role = str(row["role"])
        msg_type = str(row.get("msg_type", ""))
        content = str(row.get("content", "")).strip()
        if role == "assistant" and msg_type == "1" and content:
            cur += 1
        else:
            if cur > 0:
                run_lengths.append(cur)
                cur = 0
    if cur > 0:
        run_lengths.append(cur)

    stats: dict[str, Any] = {
        "assistant_text_count": len(clean_rows),
        "avg_len": round(statistics.fmean(lengths), 2) if lengths else 0.0,
        "median_len": lengths_sorted[len(lengths_sorted) // 2] if lengths else 0,
        "p90_len": lengths_sorted[min(int(len(lengths_sorted) * 0.9), len(lengths_sorted) - 1)] if lengths else 0,
        "p99_len": lengths_sorted[min(int(len(lengths_sorted) * 0.99), len(lengths_sorted) - 1)] if lengths else 0,
        "short_le6_ratio": round(sum(1 for x in lengths if x <= 6) / len(lengths), 4) if lengths else 0.0,
        "question_ratio": round(
            sum(1 for r in clean_rows if QUESTION_RE.search(str(r["content"]))) / len(clean_rows), 4
        )
        if clean_rows
        else 0.0,
        "exclaim_ratio": round(
            sum(1 for r in clean_rows if EXCLAIM_RE.search(str(r["content"]))) / len(clean_rows), 4
        )
        if clean_rows
        else 0.0,
        "laugh_ratio": round(
            sum(1 for r in clean_rows if LAUGH_RE.search(str(r["content"]))) / len(clean_rows), 4
        )
        if clean_rows
        else 0.0,
        "tilde_ratio": round(
            sum(1 for r in clean_rows if ("~" in str(r["content"]) or "～" in str(r["content"])))
            / len(clean_rows),
            4,
        )
        if clean_rows
        else 0.0,
        "top_tokens": tokens.most_common(200),
        "top_prefix2": prefix2.most_common(40),
        "top_suffix2": suffix2.most_common(40),
        "run_avg": round(statistics.fmean(run_lengths), 2) if run_lengths else 1.0,
        "run_p90": sorted(run_lengths)[min(int(len(run_lengths) * 0.9), len(run_lengths) - 1)]
        if run_lengths
        else 1,
        "nickname_policy": {
            "strict_only": settings.strict_nickname,
            "forbidden": settings.forbidden_nicknames,
        },
    }
    return stats


def _default_preference_profile(style_profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "version_note": "bootstrap",
        "weights": {
            "semantic": 0.45,
            "style": 0.22,
            "relation": 0.12,
            "recency": 0.08,
            "online_memory": 0.13,
        },
        "tone": {
            "laugh_ratio_target": style_profile.get("laugh_ratio", 0.1),
            "tilde_ratio_target": style_profile.get("tilde_ratio", 0.03),
            "question_ratio_target": style_profile.get("question_ratio", 0.03),
        },
        "multi_bubble": {
            "default_count": 2,
            "max_count": 4,
            "run_avg_target": style_profile.get("run_avg", 2.5),
        },
        "nickname": {
            "strict_only": settings.strict_nickname,
            "forbidden": settings.forbidden_nicknames,
        },
        "master_persona": {
            "style_anchor": "短句、口语、连发、轻松亲密、少说教",
            "behavior_anchor": "先承接情绪和当下需求，再补充信息",
            "risk_anchor": "不编造关键事实，不切换客服腔，只允许“宝贝”称呼",
            "locked": True,
        },
    }


def _default_persona_profile(style_profile: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    assistant_rows = [r for r in rows if str(r.get("role", "")) == "assistant" and str(r.get("content", "")).strip()]
    phrases = Counter()
    for row in assistant_rows:
        for part in PHRASE_RE.findall(str(row.get("content", ""))):
            text = part.strip()
            if len(text) < 2:
                continue
            phrases[text] += 1

    top_phrases = [k for k, _ in phrases.most_common(40)]
    return {
        "version_note": "bootstrap_persona",
        "core_persona": {
            "identity": {
                "name": settings.app_name,
                "target_sender": settings.target_sender,
                "role": "relationship_chat_partner",
            },
            "relationship": {
                "primary_user_aliases": settings.user_sender_candidates,
                "strict_nickname": settings.strict_nickname,
                "forbidden_nicknames": settings.forbidden_nicknames,
            },
            "anchors": {
                "style": "短句、口语、连发、先回应当下语境",
                "behavior": "先接住用户此刻的具体问题，再补充情绪或信息",
                "risk": "不偏题，不突然切换客服/教程口吻，不发散无关内容",
            },
            "guardrails": {
                "must_stay_on_context": True,
                "allow_soft_repair": True,
                "fallback_style": "先承接语境，再简短确认，不机械道歉",
            },
            "locked": True,
        },
        "adaptive_persona": {
            "speech_traits": {
                "avg_len": style_profile.get("avg_len", 0.0),
                "run_avg": style_profile.get("run_avg", 1.0),
                "laugh_ratio": style_profile.get("laugh_ratio", 0.0),
                "tilde_ratio": style_profile.get("tilde_ratio", 0.0),
                "question_ratio": style_profile.get("question_ratio", 0.0),
                "top_phrases": top_phrases,
            },
            "updated_from_feedback": False,
        },
    }


def _build_segments_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Keep only usable text rows first.
    usable = [
        r
        for r in rows
        if str(r.get("msg_type", "")) == "1"
        and int(r.get("is_garbled", 0)) == 0
        and str(r.get("content", "")).strip()
    ]
    if not usable:
        return []

    user_positions = [idx for idx, r in enumerate(usable) if str(r.get("role", "")) == "user"]
    if not user_positions:
        return []

    win_before = max(1, settings.segment_window_before)
    win_after = max(1, settings.segment_window_after)
    max_lines = max(4, settings.segment_max_lines)

    segments: list[dict[str, Any]] = []

    for anchor_order, pos in enumerate(user_positions):
        anchor = usable[pos]
        anchor_id = int(anchor["id"])
        anchor_text = str(anchor["content"]).strip()
        if not anchor_text:
            continue

        left = max(0, pos - win_before)
        right = min(len(usable) - 1, pos + win_after)

        # Prefer ending at assistant run after anchor, if available.
        run_end = pos
        j = pos + 1
        while j <= right and str(usable[j].get("role", "")) == "assistant":
            run_end = j
            j += 1
        if run_end > pos:
            right = run_end

        lines = usable[left : right + 1]
        if len(lines) > max_lines:
            anchor_rel = pos - left
            keep_left = max(0, anchor_rel - (max_lines // 2))
            keep_right = keep_left + max_lines
            if keep_right > len(lines):
                keep_right = len(lines)
                keep_left = max(0, keep_right - max_lines)
            lines = lines[keep_left:keep_right]

        segment_text = "\n".join([f"{ln['role']}: {str(ln['content']).strip()}" for ln in lines])
        if not segment_text:
            continue

        segments.append(
            {
                "anchor_user_id": anchor_id,
                "anchor_text": anchor_text,
                "segment_text": segment_text,
                "start_msg_id": int(lines[0]["id"]),
                "end_msg_id": int(lines[-1]["id"]),
                "anchor_timestamp_unix": anchor.get("timestamp_unix"),
                "line_count": len(lines),
                "created_at": utc_now_iso(),
            }
        )

        if (anchor_order + 1) % 20000 == 0:
            logger.info("segment_build_progress anchors=%d", anchor_order + 1)

    return segments


def _rebuild_segments(conn) -> int:
    rows = conn.execute(
        """
        SELECT id, role, msg_type, is_garbled, content, timestamp_unix
        FROM baseline_messages
        ORDER BY id ASC
        """
    ).fetchall()
    segments = _build_segments_from_rows(rows)

    if not segments:
        return 0

    conn.execute("DELETE FROM baseline_segments")
    conn.executemany(
        """
        INSERT INTO baseline_segments
          (anchor_user_id, anchor_text, segment_text, start_msg_id, end_msg_id, anchor_timestamp_unix, line_count, created_at)
        VALUES
          (:anchor_user_id, :anchor_text, :segment_text, :start_msg_id, :end_msg_id, :anchor_timestamp_unix, :line_count, :created_at)
        """,
        segments,
    )
    conn.execute("DELETE FROM segment_embeddings")
    return len(segments)


def _ensure_profiles(conn) -> tuple[int, int, int]:
    style_row = conn.execute("SELECT version FROM profiles WHERE profile_type='style'").fetchone()
    pref_row = conn.execute("SELECT version FROM profiles WHERE profile_type='preference'").fetchone()
    persona_row = conn.execute("SELECT version FROM persona_profiles WHERE profile_key='default'").fetchone()

    if style_row and pref_row and persona_row:
        row = db.get_persona_profile()
        if row:
            normalized = normalize_persona_payload(row.get("payload"))
            if normalized != row.get("payload"):
                db.upsert_persona_profile(normalized, bump_version=True)
                fresh = db.get_persona_profile()
                return int(style_row["version"]), int(pref_row["version"]), int(fresh["version"]) if fresh else int(persona_row["version"])
        return int(style_row["version"]), int(pref_row["version"]), int(persona_row["version"])

    rows = conn.execute(
        """
        SELECT role, msg_type, is_garbled, content
        FROM baseline_messages
        ORDER BY id ASC
        """
    ).fetchall()
    style_profile = _compute_style_profile(rows)
    preference_profile = _default_preference_profile(style_profile)
    persona_profile = _default_persona_profile(style_profile, rows)

    db.upsert_profile("style", style_profile)
    db.upsert_profile("preference", preference_profile)
    db.upsert_persona_profile(persona_profile)

    settings.style_profile_path.parent.mkdir(parents=True, exist_ok=True)
    settings.preference_profile_path.parent.mkdir(parents=True, exist_ok=True)
    settings.persona_profile_path.parent.mkdir(parents=True, exist_ok=True)
    settings.style_profile_path.write_text(
        json.dumps(style_profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    settings.preference_profile_path.write_text(
        json.dumps(preference_profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    settings.persona_profile_path.write_text(
        json.dumps(persona_profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    persona = db.get_persona_profile()
    return 1, 1, int(persona["version"]) if persona else 1


def bootstrap_if_needed() -> dict[str, Any]:
    db.init_schema()

    with db.connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM baseline_messages").fetchone()
        baseline_count = int(row["c"]) if row else 0

    bootstrapped = False
    role_counts: dict[str, int] = {}

    if baseline_count == 0:
        if not settings.chat_data_path.exists():
            logger.warning(
                "chat data missing, continue with empty baseline: %s",
                settings.chat_data_path,
            )
            with db.connect() as conn:
                style_ver, pref_ver, persona_ver = _ensure_profiles(conn)
                seg_row = conn.execute("SELECT COUNT(*) AS c FROM baseline_segments").fetchone()
                segments_count = int(seg_row["c"]) if seg_row else 0
            return {
                "baseline_messages": 0,
                "segments": segments_count,
                "style_profile_version": style_ver,
                "preference_profile_version": pref_ver,
                "persona_profile_version": persona_ver,
                "bootstrapped": False,
                "bootstrap_source": "empty_without_chat_data",
            }

        raw_rows = json.loads(Path(settings.chat_data_path).read_text(encoding="utf-8"))
        normalized_rows: list[dict[str, Any]] = []
        now = utc_now_iso()
        user_candidates = set(settings.user_sender_candidates)

        for item in raw_rows:
            sender = str(item.get("sender") or "").strip() or "Unknown"
            content = str(item.get("content") or "")
            msg_type = item.get("msg_type")
            role = _normalize_role(sender, settings.target_sender, user_candidates)
            is_garbled = 1 if GARBLE_RE.search(content) else 0
            ts_raw = str(item.get("timestamp_raw") or "")
            normalized_rows.append(
                {
                    "msg_id": item.get("msg_id"),
                    "sender": sender,
                    "msg_type": str(msg_type) if msg_type is not None else "",
                    "timestamp_raw": ts_raw,
                    "timestamp_unix": parse_timestamp_to_unix(ts_raw),
                    "role": role,
                    "content": content.strip(),
                    "is_garbled": is_garbled,
                    "created_at": now,
                }
            )
            role_counts[role] = role_counts.get(role, 0) + 1

        with db.connect() as conn:
            conn.executemany(
                """
                INSERT INTO baseline_messages
                  (msg_id, sender, msg_type, timestamp_raw, timestamp_unix, role, content, is_garbled, created_at)
                VALUES
                  (:msg_id, :sender, :msg_type, :timestamp_raw, :timestamp_unix, :role, :content, :is_garbled, :created_at)
                """,
                normalized_rows,
            )

            segments_count = _rebuild_segments(conn)

        style_profile = _compute_style_profile(normalized_rows)
        preference_profile = _default_preference_profile(style_profile)
        persona_profile = _default_persona_profile(style_profile, normalized_rows)
        db.upsert_profile("style", style_profile)
        db.upsert_profile("preference", preference_profile)
        db.upsert_persona_profile(persona_profile)

        settings.style_profile_path.parent.mkdir(parents=True, exist_ok=True)
        settings.preference_profile_path.parent.mkdir(parents=True, exist_ok=True)
        settings.persona_profile_path.parent.mkdir(parents=True, exist_ok=True)
        settings.style_profile_path.write_text(
            json.dumps(style_profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        settings.preference_profile_path.write_text(
            json.dumps(preference_profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        settings.persona_profile_path.write_text(
            json.dumps(persona_profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        baseline_count = len(normalized_rows)
        bootstrapped = True
    else:
        with db.connect() as conn:
            style_ver, pref_ver, persona_ver = _ensure_profiles(conn)
            seg_row = conn.execute("SELECT COUNT(*) AS c FROM baseline_segments").fetchone()
            segments_count = int(seg_row["c"]) if seg_row else 0
            if segments_count == 0:
                segments_count = _rebuild_segments(conn)
            return {
                "baseline_messages": baseline_count,
                "segments": segments_count,
                "style_profile_version": style_ver,
                "preference_profile_version": pref_ver,
                "persona_profile_version": persona_ver,
                "bootstrapped": False,
            }

    style = db.get_profile("style")
    pref = db.get_profile("preference")
    persona = db.get_persona_profile()
    with db.connect() as conn:
        seg_row = conn.execute("SELECT COUNT(*) AS c FROM baseline_segments").fetchone()
        segments_count = int(seg_row["c"]) if seg_row else 0

    return {
        "baseline_messages": baseline_count,
        "segments": segments_count,
        "role_counts": role_counts,
        "style_profile_version": style["version"] if style else 0,
        "preference_profile_version": pref["version"] if pref else 0,
        "persona_profile_version": persona["version"] if persona else 0,
        "bootstrapped": bootstrapped,
    }
