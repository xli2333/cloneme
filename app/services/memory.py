from __future__ import annotations

import json
from typing import Any

from ..db import db, utc_now_iso


class MemoryService:
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        payload = json.dumps(metadata or {}, ensure_ascii=False)
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO online_conversations
                  (conversation_id, role, content, message_type, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, role, content, message_type, payload, utc_now_iso()),
            )
            row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
        return int(row["id"])

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


memory_service = MemoryService()

