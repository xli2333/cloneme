from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import settings
from ..db import db
from .semantic_index import semantic_index_service

WORD_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]{1,24}")
logger = logging.getLogger("doppelganger.retrieval")


def _cjk_ngrams(text: str, n_values: tuple[int, ...] = (2, 3)) -> list[str]:
    chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
    grams: list[str] = []
    for n in n_values:
        for i in range(0, max(0, len(chars) - n + 1)):
            grams.append("".join(chars[i : i + n]))
    out: list[str] = []
    seen: set[str] = set()
    for g in grams:
        if g and g not in seen:
            seen.add(g)
            out.append(g)
    return out


def _to_fts_query(text: str) -> str:
    tokens = WORD_RE.findall(text.lower())
    uniq: list[str] = []
    for token in tokens:
        if token in uniq:
            continue
        uniq.append(token)
        if len(uniq) >= 12:
            break
    if not uniq:
        return ""
    return " OR ".join(uniq)


def _lexical_rank_to_score(rank: float) -> float:
    if rank <= 0:
        return 1.0
    return 1.0 / (1.0 + rank)


def _dynamic_window(query_text: str, before: int, after: int) -> tuple[int, int]:
    if not settings.rag_dynamic_window_enabled:
        return before, after
    text_len = len(query_text.strip())
    token_count = len(WORD_RE.findall(query_text))
    complexity = max(text_len // 20, token_count // 8)
    extra = max(0, min(settings.rag_dynamic_window_extra, complexity))
    return before + extra, after + extra


class RetrievalService:
    def _query_segment_hits_lexical(
        self,
        conn,
        query_text: str,
        limit: int,
        persona_key: str,
    ) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        fts = _to_fts_query(query_text)
        if fts:
            rows = conn.execute(
                """
                SELECT s.id, s.anchor_text, s.anchor_timestamp_unix, bm25(baseline_segments_fts) AS rank
                FROM baseline_segments_fts
                JOIN baseline_segments s ON s.id = baseline_segments_fts.rowid
                WHERE baseline_segments_fts MATCH ?
                  AND s.persona_key = ?
                ORDER BY rank ASC, s.id DESC
                LIMIT ?
                """,
                (fts, persona_key, limit),
            ).fetchall()
            hits.extend(rows)

        grams = _cjk_ngrams(query_text)[:10]
        if grams:
            where = " OR ".join(["anchor_text LIKE ?"] * len(grams))
            rows2 = conn.execute(
                f"""
                SELECT id, anchor_text, anchor_timestamp_unix, 10000.0 AS rank
                FROM baseline_segments
                WHERE {where}
                  AND persona_key = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                [*([f"%{g}%" for g in grams]), persona_key, limit],
            ).fetchall()
            hits.extend(rows2)

        if not hits:
            rows3 = conn.execute(
                """
                SELECT id, anchor_text, anchor_timestamp_unix, 20000.0 AS rank
                FROM baseline_segments
                WHERE persona_key = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (persona_key, limit),
            ).fetchall()
            hits.extend(rows3)

        dedup: dict[int, dict[str, Any]] = {}
        for row in hits:
            sid = int(row["id"])
            cur = dedup.get(sid)
            if cur is None or float(row["rank"]) < float(cur["lexical_rank"]):
                dedup[sid] = {
                    "segment_id": sid,
                    "anchor_text": str(row["anchor_text"]),
                    "anchor_timestamp_unix": row.get("anchor_timestamp_unix"),
                    "lexical_rank": float(row["rank"]),
                }
        return list(dedup.values())

    def get_recent_messages(self, conversation_id: str, limit: int = 30) -> list[dict[str, Any]]:
        with db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, role, content, message_type, feedback_score, created_at
                FROM online_conversations
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        rows.reverse()
        return rows

    def retrieve_online_memory(self, conversation_id: str, query_text: str, k: int = 12) -> list[dict[str, Any]]:
        fts = _to_fts_query(query_text)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.online_memory_days)).isoformat()

        if fts:
            with db.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT c.id, c.role, c.content, c.created_at, bm25(online_conversations_fts) AS rank
                    FROM online_conversations_fts
                    JOIN online_conversations c ON c.id = online_conversations_fts.rowid
                    WHERE online_conversations_fts MATCH ?
                      AND c.conversation_id = ?
                      AND c.created_at >= ?
                    ORDER BY rank ASC, c.id DESC
                    LIMIT ?
                    """,
                    (fts, conversation_id, cutoff, k),
                ).fetchall()
            if rows:
                return rows

        return self.get_recent_messages(conversation_id, limit=min(k, 12))

    def retrieve_baseline_style(
        self,
        query_text: str,
        k: int = 24,
        *,
        persona_key: str | None = None,
    ) -> list[dict[str, Any]]:
        persona_key = (persona_key or settings.dxa_persona_key).strip() or settings.dxa_persona_key
        # Style references are sampled from top semantic segments' assistant lines.
        segments = self.retrieve_similar_segments(
            query_text,
            top_k_hits=max(2, k // 6),
            persona_key=persona_key,
        )
        lines: list[dict[str, Any]] = []
        for seg in segments:
            for ln in seg.get("lines", []):
                if ln.get("role") == "assistant" and str(ln.get("content", "")).strip():
                    lines.append(
                        {
                            "id": int(ln.get("id", 0)),
                            "content": str(ln.get("content", "")),
                            "timestamp_unix": None,
                        }
                    )
                if len(lines) >= k:
                    break
            if len(lines) >= k:
                break
        return lines[:k]

    def retrieve_similar_segments(
        self,
        query_text: str,
        *,
        top_k_hits: int = 6,
        window_before: int | None = None,
        window_after: int | None = None,
        persona_key: str | None = None,
    ) -> list[dict[str, Any]]:
        query_text = query_text.strip()
        if not query_text:
            return []
        persona_key = (persona_key or settings.dxa_persona_key).strip() or settings.dxa_persona_key

        window_before = settings.segment_window_before if window_before is None else window_before
        window_after = settings.segment_window_after if window_after is None else window_after
        window_before, window_after = _dynamic_window(query_text, int(window_before), int(window_after))

        with db.connect() as conn:
            lexical_hits = self._query_segment_hits_lexical(
                conn,
                query_text,
                settings.semantic_lexical_pool,
                persona_key,
            )

            semantic_hits = []
            if settings.semantic_enabled:
                try:
                    semantic_hits = semantic_index_service.search(
                        query_text,
                        top_k=max(top_k_hits, settings.semantic_recall_k),
                        persona_key=persona_key,
                    )
                except Exception as exc:
                    logger.warning("semantic_search_failed error=%s", exc)
                    semantic_hits = []

            merged: dict[int, dict[str, Any]] = {}
            for hit in lexical_hits:
                sid = int(hit["segment_id"])
                merged[sid] = {
                    "segment_id": sid,
                    "anchor_text": hit.get("anchor_text", ""),
                    "anchor_timestamp_unix": hit.get("anchor_timestamp_unix"),
                    "lexical_rank": float(hit.get("lexical_rank", 99999.0)),
                    "semantic_score": 0.0,
                }

            for hit in semantic_hits:
                sid = int(hit["segment_id"])
                if sid not in merged:
                    row = conn.execute(
                        """
                        SELECT anchor_text, anchor_timestamp_unix
                        FROM baseline_segments
                        WHERE id = ? AND persona_key = ?
                        """,
                        (sid, persona_key),
                    ).fetchone()
                    if not row:
                        continue
                    merged[sid] = {
                        "segment_id": sid,
                        "anchor_text": str(row["anchor_text"]),
                        "anchor_timestamp_unix": row.get("anchor_timestamp_unix"),
                        "lexical_rank": 99999.0,
                        "semantic_score": float(hit.get("semantic_score", 0.0)),
                    }
                else:
                    merged[sid]["semantic_score"] = float(hit.get("semantic_score", 0.0))

            # If many lexical hits have no compatible embedding yet, autofill a capped subset
            # so retrieval quality can improve before full index build completes.
            if settings.semantic_enabled and settings.semantic_autofill_missing:
                lexical_ids = [int(x["segment_id"]) for x in lexical_hits[: settings.semantic_autofill_per_query]]
                if lexical_ids:
                    try:
                        fill_result = semantic_index_service.ensure_embeddings_for_segments(
                            lexical_ids,
                            max_items=settings.semantic_autofill_per_query,
                            refresh_dense=False,
                        )
                        if int(fill_result.get("written", 0)) > 0:
                            logger.info(
                                "semantic_autofill_triggered checked=%d written=%d",
                                int(fill_result.get("checked", 0)),
                                int(fill_result.get("written", 0)),
                            )
                    except Exception as exc:
                        logger.warning("semantic_autofill_failed error=%s", exc)

            missing_semantic = [sid for sid, item in merged.items() if float(item.get("semantic_score", 0.0)) == 0.0]
            if missing_semantic and settings.semantic_enabled:
                try:
                    score_map = semantic_index_service.semantic_scores_for_segment_ids(query_text, missing_semantic)
                    for sid, score in score_map.items():
                        merged[sid]["semantic_score"] = float(score)
                except Exception as exc:
                    logger.warning("semantic_score_fill_failed error=%s", exc)

            ts_values = [int(v.get("anchor_timestamp_unix") or 0) for v in merged.values()]
            max_ts = max(ts_values) if ts_values else 0
            min_ts = min(ts_values) if ts_values else 0
            span = max(1, max_ts - min_ts)

            ranked: list[dict[str, Any]] = []
            for item in merged.values():
                semantic = float(item.get("semantic_score", 0.0))
                lexical = _lexical_rank_to_score(float(item.get("lexical_rank", 99999.0)))
                ts = int(item.get("anchor_timestamp_unix") or 0)
                recency = (ts - min_ts) / span if ts else 0.0
                total = 0.72 * semantic + 0.18 * lexical + 0.10 * recency
                ranked.append(
                    {
                        **item,
                        "semantic_score": semantic,
                        "lexical_score": lexical,
                        "recency_score": recency,
                        "retrieval_score": total,
                    }
                )

            ranked.sort(key=lambda x: (-x["retrieval_score"], -x["semantic_score"], x["lexical_rank"], -x["segment_id"]))
            chosen = ranked[: max(1, top_k_hits)]

            segments: list[dict[str, Any]] = []
            for hit in chosen:
                sid = int(hit["segment_id"])
                seg_row = conn.execute(
                    """
                    SELECT id, anchor_user_id, anchor_text, start_msg_id, end_msg_id, line_count
                    FROM baseline_segments
                    WHERE id = ? AND persona_key = ?
                    """,
                    (sid, persona_key),
                ).fetchone()
                if not seg_row:
                    continue

                # Allow temporary override of window in debug paths.
                start_id = int(seg_row["start_msg_id"])
                end_id = int(seg_row["end_msg_id"])
                if window_before != settings.segment_window_before or window_after != settings.segment_window_after:
                    anchor_id = int(seg_row["anchor_user_id"])
                    start_id = max(1, anchor_id - max(1, int(window_before)))
                    end_id = anchor_id + max(1, int(window_after))

                lines_rows = conn.execute(
                    """
                    SELECT id, role, sender, content, msg_type, timestamp_raw
                    FROM baseline_messages
                    WHERE id BETWEEN ? AND ?
                      AND persona_key = ?
                      AND msg_type = '1'
                      AND is_garbled = 0
                    ORDER BY id ASC
                    """,
                    (start_id, end_id, persona_key),
                ).fetchall()

                lines = [
                    {
                        "id": int(r["id"]),
                        "role": str(r["role"]),
                        "sender": str(r["sender"]),
                        "content": str(r["content"]),
                        "timestamp_raw": str(r.get("timestamp_raw") or ""),
                    }
                    for r in lines_rows
                    if str(r.get("content", "")).strip()
                ]
                if settings.rag_max_segment_chars > 0:
                    max_chars = int(settings.rag_max_segment_chars)
                    trimmed: list[dict[str, Any]] = []
                    used = 0
                    for item in lines:
                        content = str(item.get("content", ""))
                        # Include role/sender overhead so the cap tracks real prompt size.
                        cost = len(content) + len(str(item.get("role", ""))) + 3
                        if trimmed and used + cost > max_chars:
                            break
                        trimmed.append(item)
                        used += cost
                    lines = trimmed
                if not lines:
                    continue

                segments.append(
                    {
                        "segment_id": sid,
                        "anchor_id": int(seg_row["anchor_user_id"]),
                        "anchor_text": str(seg_row["anchor_text"]),
                        "line_count": int(seg_row["line_count"]),
                        "semantic_score": float(hit["semantic_score"]),
                        "lexical_score": float(hit["lexical_score"]),
                        "recency_score": float(hit["recency_score"]),
                        "retrieval_score": float(hit["retrieval_score"]),
                        "lines": lines,
                    }
                )

        if segments:
            top = segments[0]
            logger.info(
                "rag_segment_top persona=%s seg_id=%s score=%.4f semantic=%.4f lexical=%.4f window=%d/%d anchor=%s",
                persona_key,
                top.get("segment_id"),
                float(top.get("retrieval_score", 0.0)),
                float(top.get("semantic_score", 0.0)),
                float(top.get("lexical_score", 0.0)),
                int(window_before),
                int(window_after),
                str(top.get("anchor_text", ""))[:120],
            )
            logger.info(
                "rag_segment_ranked=%s",
                [
                    {
                        "seg_id": int(s.get("segment_id", 0)),
                        "score": round(float(s.get("retrieval_score", 0.0)), 4),
                        "semantic": round(float(s.get("semantic_score", 0.0)), 4),
                        "lexical": round(float(s.get("lexical_score", 0.0)), 4),
                        "anchor": str(s.get("anchor_text", ""))[:28],
                    }
                    for s in segments[:6]
                ],
            )
        return segments

    def fetch_fact_cards(self, query_text: str, k: int = 10, *, persona_key: str | None = None) -> list[str]:
        segments = self.retrieve_similar_segments(
            query_text,
            top_k_hits=max(1, k // 2),
            persona_key=persona_key,
        )
        facts: list[str] = []
        for seg in segments:
            for line in seg.get("lines", []):
                if line.get("role") == "assistant":
                    text = str(line.get("content", "")).strip()
                    if len(text) >= 8:
                        facts.append(text)
                if len(facts) >= k:
                    break
            if len(facts) >= k:
                break
        return facts[:k]


retrieval_service = RetrievalService()
