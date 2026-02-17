from __future__ import annotations

import json
import re
from typing import Any

from ..db import db, utc_now_iso

FOLLOWUP_EXPLICIT_RE = re.compile(
    r"(明天|后天|下周|下周一|下周二|下周三|下周四|下周五|周末|今晚|稍后|回头|等会|待会)",
    flags=re.IGNORECASE,
)


class MemoryService:
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        now = utc_now_iso()
        payload = json.dumps(metadata or {}, ensure_ascii=False)
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO online_conversations
                  (conversation_id, role, content, message_type, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, role, content, message_type, payload, now),
            )
            row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
        return int(row["id"])

    def get_message_meta(self, message_id: int) -> dict[str, Any] | None:
        with db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, conversation_id, role, content, created_at, metadata_json
                FROM online_conversations
                WHERE id = ?
                """,
                (int(message_id),),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        try:
            payload["metadata"] = json.loads(str(row.get("metadata_json") or "{}"))
        except Exception:
            payload["metadata"] = {}
        return payload

    def get_recent_role_messages(
        self,
        conversation_id: str,
        role: str,
        *,
        limit: int = 2,
    ) -> list[dict[str, Any]]:
        with db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, role, content, created_at
                FROM online_conversations
                WHERE conversation_id = ? AND role = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, role, max(1, int(limit))),
            ).fetchall()
        return rows

    def add_feedback(self, conversation_id: str, message_ids: list[int], comment: str) -> int:
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO feedback_events(conversation_id, message_ids_json, comment, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, json.dumps(message_ids, ensure_ascii=False), comment, utc_now_iso()),
            )
            conn.execute(
                f"""
                UPDATE online_conversations
                SET feedback_score = feedback_score + 1
                WHERE conversation_id = ?
                  AND id IN ({",".join("?" for _ in message_ids)})
                """,
                [conversation_id, *message_ids],
            )
            row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
        return int(row["id"])

    def list_messages(self, conversation_id: str, limit: int = 120) -> list[dict[str, Any]]:
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

    def search_messages(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        pattern = f"%{query}%"
        with db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, conversation_id, role, content, created_at
                FROM online_conversations
                WHERE content LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (pattern, limit),
            ).fetchall()
        return rows

    def save_candidates(
        self,
        conversation_id: str,
        user_message_id: int,
        candidates: list[dict[str, Any]],
        selected_index: int,
    ) -> None:
        with db.connect() as conn:
            for idx, candidate in enumerate(candidates):
                conn.execute(
                    """
                    INSERT INTO generated_candidates
                      (conversation_id, user_message_id, candidate_json, score, selected, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        conversation_id,
                        user_message_id,
                        json.dumps(candidate, ensure_ascii=False),
                        float(candidate.get("total_score", 0)),
                        1 if idx == selected_index else 0,
                        utc_now_iso(),
                    ),
                )

    def get_time_state(self, conversation_id: str) -> dict[str, Any] | None:
        db.init_schema()
        with db.connect() as conn:
            row = conn.execute(
                """
                SELECT conversation_id, persona_key, last_user_at, last_assistant_at, last_time_ack_at, last_topic_summary, updated_at
                FROM conversation_time_state
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
        return row

    def upsert_time_state(
        self,
        *,
        conversation_id: str,
        persona_key: str,
        last_user_at: str | None = None,
        last_assistant_at: str | None = None,
        last_time_ack_at: str | None = None,
        last_topic_summary: str | None = None,
    ) -> None:
        db.init_schema()
        now = utc_now_iso()
        with db.connect() as conn:
            existing = conn.execute(
                """
                SELECT conversation_id, persona_key, last_user_at, last_assistant_at, last_time_ack_at, last_topic_summary
                FROM conversation_time_state
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO conversation_time_state(
                      conversation_id, persona_key, last_user_at, last_assistant_at, last_time_ack_at, last_topic_summary, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        conversation_id,
                        persona_key,
                        last_user_at,
                        last_assistant_at,
                        last_time_ack_at,
                        last_topic_summary or "",
                        now,
                    ),
                )
                return

            merged_last_user_at = last_user_at if last_user_at is not None else existing.get("last_user_at")
            merged_last_assistant_at = (
                last_assistant_at if last_assistant_at is not None else existing.get("last_assistant_at")
            )
            merged_last_time_ack_at = (
                last_time_ack_at if last_time_ack_at is not None else existing.get("last_time_ack_at")
            )
            merged_topic = last_topic_summary if last_topic_summary is not None else existing.get("last_topic_summary")
            conn.execute(
                """
                UPDATE conversation_time_state
                SET persona_key = ?, last_user_at = ?, last_assistant_at = ?, last_time_ack_at = ?, last_topic_summary = ?, updated_at = ?
                WHERE conversation_id = ?
                """,
                (
                    persona_key,
                    merged_last_user_at,
                    merged_last_assistant_at,
                    merged_last_time_ack_at,
                    merged_topic or "",
                    now,
                    conversation_id,
                ),
            )

    def _infer_followup_due_label(self, content: str) -> str | None:
        m = FOLLOWUP_EXPLICIT_RE.search(str(content))
        if not m:
            return None
        return m.group(1)

    def maybe_add_followup(
        self,
        *,
        conversation_id: str,
        persona_key: str,
        source_message_id: int,
        owner_role: str,
        content: str,
    ) -> None:
        db.init_schema()
        due_label = self._infer_followup_due_label(content)
        if not due_label:
            return
        topic = str(content).strip()
        if len(topic) > 120:
            topic = topic[:120] + "…"
        now = utc_now_iso()
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO conversation_followups(
                  conversation_id, persona_key, source_message_id, owner_role, topic, due_at, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (
                    conversation_id,
                    persona_key,
                    int(source_message_id),
                    owner_role,
                    topic,
                    due_label,
                    now,
                    now,
                ),
            )

    def list_open_followups(self, conversation_id: str, limit: int = 8) -> list[dict[str, Any]]:
        db.init_schema()
        with db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, conversation_id, persona_key, source_message_id, owner_role, topic, due_at, status, created_at, updated_at
                FROM conversation_followups
                WHERE conversation_id = ? AND status = 'open'
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, max(1, int(limit))),
            ).fetchall()
        return rows


memory_service = MemoryService()
