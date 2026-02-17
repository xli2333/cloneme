from __future__ import annotations

import json
import logging
import re
import statistics
from collections import Counter
from dataclasses import dataclass
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
TS_CORE_RE = re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}\s+\d{1,2}:\d{2}:\d{2}(?:\s+[AP]M)?", flags=re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class PersonaBootstrapSource:
    key: str
    data_paths: list[Path]
    strict_nickname: str
    forbidden_nicknames: list[str]
    user_aliases: list[str]
    role_name: str
    style_anchor: str
    behavior_anchor: str
    risk_anchor: str


def _persona_sources() -> list[PersonaBootstrapSource]:
    dxa_key = settings.dxa_persona_key
    friends_key = settings.friends_persona_key
    return [
        PersonaBootstrapSource(
            key=dxa_key,
            data_paths=[settings.chat_data_path],
            strict_nickname=settings.strict_nickname,
            forbidden_nicknames=list(settings.forbidden_nicknames),
            user_aliases=list(settings.user_sender_candidates),
            role_name="relationship_chat_partner",
            style_anchor="短句、口语、连发、轻松亲密、少说教",
            behavior_anchor="先承接情绪和当下需求，再补充信息",
            risk_anchor="不编造关键事实，不切换客服腔，只允许固定称呼",
        ),
        PersonaBootstrapSource(
            key=friends_key,
            data_paths=list(settings.friends_chat_data_paths),
            strict_nickname=settings.friends_strict_nickname,
            forbidden_nicknames=list(settings.friends_forbidden_nicknames),
            user_aliases=list(settings.friends_user_sender_candidates),
            role_name="friend_chat_partner",
            style_anchor="短句、口语、连发、朋友式自然互动",
            behavior_anchor="先接住当下语境，再给可继续聊的回应",
            risk_anchor="不使用恋爱向固定昵称，不跑题，不切换教程腔",
        ),
    ]


def parse_timestamp_to_unix(raw: str) -> int | None:
    if not raw:
        return None
    text = str(raw).strip()
    m = TS_CORE_RE.search(text)
    if m:
        text = m.group(0).strip()
    fmts = [
        "%Y-%m-%d %I:%M:%S %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %I:%M:%S %p",
        "%Y/%m/%d %H:%M:%S",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(text, fmt)
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


def _compute_style_profile(
    rows: list[dict[str, Any]],
    *,
    strict_nickname: str,
    forbidden_nicknames: list[str],
) -> dict[str, Any]:
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

    return {
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
            "strict_only": strict_nickname,
            "forbidden": forbidden_nicknames,
        },
    }


def _default_preference_profile(
    style_profile: dict[str, Any],
    source: PersonaBootstrapSource,
) -> dict[str, Any]:
    return {
        "version_note": f"bootstrap:{source.key}",
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
            "strict_only": source.strict_nickname,
            "forbidden": source.forbidden_nicknames,
        },
        "master_persona": {
            "style_anchor": source.style_anchor,
            "behavior_anchor": source.behavior_anchor,
            "risk_anchor": source.risk_anchor,
            "locked": True,
        },
    }


def _default_persona_profile(
    style_profile: dict[str, Any],
    rows: list[dict[str, Any]],
    source: PersonaBootstrapSource,
) -> dict[str, Any]:
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
        "version_note": f"bootstrap_persona:{source.key}",
        "core_persona": {
            "identity": {
                "name": settings.app_name,
                "target_sender": settings.target_sender,
                "role": source.role_name,
            },
            "relationship": {
                "primary_user_aliases": source.user_aliases,
                "strict_nickname": source.strict_nickname,
                "forbidden_nicknames": source.forbidden_nicknames,
            },
            "anchors": {
                "style": "短句、口语、连发、先回应当下语境",
                "behavior": "先接住用户此刻的具体问题，再补充情绪或信息",
                "risk": source.risk_anchor,
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


def _build_segments_from_rows(rows: list[dict[str, Any]], persona_key: str) -> list[dict[str, Any]]:
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
                "persona_key": persona_key,
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
            logger.info("segment_build_progress persona=%s anchors=%d", persona_key, anchor_order + 1)

    return segments


def _read_chat_rows(data_paths: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in data_paths:
        if not path.exists():
            logger.warning("chat data missing: %s", path)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("chat data load failed path=%s error=%s", path, exc)
            continue
        if isinstance(payload, list):
            out.extend([x for x in payload if isinstance(x, dict)])
    return out


def _normalize_rows(raw_rows: list[dict[str, Any]], source: PersonaBootstrapSource) -> list[dict[str, Any]]:
    now = utc_now_iso()
    user_candidates = set(source.user_aliases)
    normalized_rows: list[dict[str, Any]] = []
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
                "persona_key": source.key,
                "role": role,
                "content": content.strip(),
                "is_garbled": is_garbled,
                "created_at": now,
            }
        )
    return normalized_rows


def _load_rows_for_persona(conn, persona_key: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT role, msg_type, is_garbled, content
        FROM baseline_messages
        WHERE persona_key = ?
        ORDER BY id ASC
        """,
        (persona_key,),
    ).fetchall()
    return rows


def _rebuild_segments_for_persona(conn, persona_key: str) -> int:
    rows = conn.execute(
        """
        SELECT id, role, msg_type, is_garbled, content, timestamp_unix
        FROM baseline_messages
        WHERE persona_key = ?
        ORDER BY id ASC
        """,
        (persona_key,),
    ).fetchall()
    segments = _build_segments_from_rows(rows, persona_key=persona_key)

    old_ids = [int(r["id"]) for r in conn.execute("SELECT id FROM baseline_segments WHERE persona_key = ?", (persona_key,)).fetchall()]
    if old_ids:
        conn.execute(
            f"DELETE FROM segment_embeddings WHERE segment_id IN ({','.join('?' for _ in old_ids)})",
            old_ids,
        )
    conn.execute("DELETE FROM baseline_segments WHERE persona_key = ?", (persona_key,))

    if not segments:
        return 0

    conn.executemany(
        """
        INSERT INTO baseline_segments
          (anchor_user_id, persona_key, anchor_text, segment_text, start_msg_id, end_msg_id, anchor_timestamp_unix, line_count, created_at)
        VALUES
          (:anchor_user_id, :persona_key, :anchor_text, :segment_text, :start_msg_id, :end_msg_id, :anchor_timestamp_unix, :line_count, :created_at)
        """,
        segments,
    )
    return len(segments)


def _upsert_profile_conn(conn, profile_type: str, payload: dict[str, Any], *, bump_version: bool = False) -> int:
    now = utc_now_iso()
    existing = conn.execute(
        "SELECT version FROM profiles WHERE profile_type = ?",
        (profile_type,),
    ).fetchone()
    if existing:
        version = int(existing["version"]) + 1 if bump_version else int(existing["version"])
        conn.execute(
            """
            UPDATE profiles
            SET payload_json = ?, version = ?, updated_at = ?
            WHERE profile_type = ?
            """,
            (json.dumps(payload, ensure_ascii=False), version, now, profile_type),
        )
        return version
    conn.execute(
        """
        INSERT INTO profiles(profile_type, payload_json, version, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (profile_type, json.dumps(payload, ensure_ascii=False), 1, now),
    )
    return 1


def _upsert_persona_profile_conn(
    conn,
    profile_key: str,
    payload: dict[str, Any],
    *,
    bump_version: bool = False,
) -> int:
    now = utc_now_iso()
    existing = conn.execute(
        "SELECT version FROM persona_profiles WHERE profile_key = ?",
        (profile_key,),
    ).fetchone()
    if existing:
        version = int(existing["version"]) + 1 if bump_version else int(existing["version"])
        conn.execute(
            """
            UPDATE persona_profiles
            SET payload_json = ?, version = ?, updated_at = ?
            WHERE profile_key = ?
            """,
            (json.dumps(payload, ensure_ascii=False), version, now, profile_key),
        )
        return version
    conn.execute(
        """
        INSERT INTO persona_profiles(profile_key, payload_json, version, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (profile_key, json.dumps(payload, ensure_ascii=False), 1, now),
    )
    return 1


def _upsert_profiles_for_persona(conn, source: PersonaBootstrapSource) -> tuple[int, int, int]:
    style_key = f"style:{source.key}"
    pref_key = f"preference:{source.key}"
    style_row = conn.execute("SELECT version FROM profiles WHERE profile_type=?", (style_key,)).fetchone()
    pref_row = conn.execute("SELECT version FROM profiles WHERE profile_type=?", (pref_key,)).fetchone()
    persona_row = conn.execute(
        "SELECT version FROM persona_profiles WHERE profile_key=?",
        (source.key,),
    ).fetchone()
    if style_row and pref_row and persona_row:
        row = conn.execute(
            "SELECT payload_json, version FROM persona_profiles WHERE profile_key = ?",
            (source.key,),
        ).fetchone()
        if row:
            payload = json.loads(str(row.get("payload_json") or "{}"))
            normalized = normalize_persona_payload(payload)
            if normalized != payload:
                ver = _upsert_persona_profile_conn(
                    conn,
                    source.key,
                    normalized,
                    bump_version=True,
                )
                return int(style_row["version"]), int(pref_row["version"]), ver
        return int(style_row["version"]), int(pref_row["version"]), int(persona_row["version"])

    rows = _load_rows_for_persona(conn, source.key)
    style_profile = _compute_style_profile(
        rows,
        strict_nickname=source.strict_nickname,
        forbidden_nicknames=source.forbidden_nicknames,
    )
    preference_profile = _default_preference_profile(style_profile, source)
    persona_profile = _default_persona_profile(style_profile, rows, source)

    style_ver = _upsert_profile_conn(conn, style_key, style_profile)
    pref_ver = _upsert_profile_conn(conn, pref_key, preference_profile)
    persona_ver = _upsert_persona_profile_conn(conn, source.key, persona_profile)

    if source.key == settings.dxa_persona_key:
        _upsert_profile_conn(conn, "style", style_profile)
        _upsert_profile_conn(conn, "preference", preference_profile)
        _upsert_persona_profile_conn(conn, "default", persona_profile)

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

    return style_ver, pref_ver, persona_ver


def _ensure_persona_baseline(conn, source: PersonaBootstrapSource) -> dict[str, Any]:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM baseline_messages WHERE persona_key = ?",
        (source.key,),
    ).fetchone()
    baseline_count = int(row["c"]) if row else 0
    ingested = 0

    if baseline_count == 0:
        raw_rows = _read_chat_rows(source.data_paths)
        normalized_rows = _normalize_rows(raw_rows, source)
        if normalized_rows:
            conn.executemany(
                """
                INSERT INTO baseline_messages
                  (msg_id, sender, msg_type, timestamp_raw, timestamp_unix, persona_key, role, content, is_garbled, created_at)
                VALUES
                  (:msg_id, :sender, :msg_type, :timestamp_raw, :timestamp_unix, :persona_key, :role, :content, :is_garbled, :created_at)
                """,
                normalized_rows,
            )
            ingested = len(normalized_rows)
            baseline_count = ingested

    seg_row = conn.execute(
        "SELECT COUNT(*) AS c FROM baseline_segments WHERE persona_key = ?",
        (source.key,),
    ).fetchone()
    segment_count = int(seg_row["c"]) if seg_row else 0
    rebuilt = False
    if baseline_count > 0 and segment_count == 0:
        segment_count = _rebuild_segments_for_persona(conn, source.key)
        rebuilt = True

    style_ver, pref_ver, persona_ver = _upsert_profiles_for_persona(conn, source)

    return {
        "persona_key": source.key,
        "baseline_messages": baseline_count,
        "ingested_messages": ingested,
        "segments": segment_count,
        "segments_rebuilt": rebuilt,
        "style_profile_version": style_ver,
        "preference_profile_version": pref_ver,
        "persona_profile_version": persona_ver,
    }


def bootstrap_if_needed() -> dict[str, Any]:
    db.init_schema()
    persona_results: list[dict[str, Any]] = []
    with db.connect() as conn:
        for source in _persona_sources():
            persona_results.append(_ensure_persona_baseline(conn, source))

        totals_row = conn.execute("SELECT COUNT(*) AS c FROM baseline_messages").fetchone()
        seg_total_row = conn.execute("SELECT COUNT(*) AS c FROM baseline_segments").fetchone()

    dxa_persona = db.get_persona_profile(settings.dxa_persona_key)
    dxa_style = db.get_profile(f"style:{settings.dxa_persona_key}")
    dxa_pref = db.get_profile(f"preference:{settings.dxa_persona_key}")
    if dxa_persona and dxa_style and dxa_pref:
        db.upsert_profile("style", dxa_style["payload"])
        db.upsert_profile("preference", dxa_pref["payload"])
        db.upsert_persona_profile(dxa_persona["payload"], profile_key="default")

    return {
        "baseline_messages": int(totals_row["c"]) if totals_row else 0,
        "segments": int(seg_total_row["c"]) if seg_total_row else 0,
        "personas": persona_results,
        "bootstrapped": any(int(item.get("ingested_messages", 0)) > 0 for item in persona_results),
    }
