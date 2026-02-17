from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from .config import settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path, timeout=60, check_same_thread=False)
        conn.row_factory = _dict_factory
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS baseline_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    msg_id INTEGER,
                    sender TEXT NOT NULL,
                    msg_type TEXT,
                    timestamp_raw TEXT,
                    timestamp_unix INTEGER,
                    persona_key TEXT NOT NULL DEFAULT 'dxa',
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    is_garbled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_baseline_sender ON baseline_messages(sender);
                CREATE INDEX IF NOT EXISTS idx_baseline_role ON baseline_messages(role);
                CREATE INDEX IF NOT EXISTS idx_baseline_ts ON baseline_messages(timestamp_unix);

                CREATE TABLE IF NOT EXISTS baseline_segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anchor_user_id INTEGER NOT NULL UNIQUE,
                    persona_key TEXT NOT NULL DEFAULT 'dxa',
                    anchor_text TEXT NOT NULL,
                    segment_text TEXT NOT NULL,
                    start_msg_id INTEGER NOT NULL,
                    end_msg_id INTEGER NOT NULL,
                    anchor_timestamp_unix INTEGER,
                    line_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(anchor_user_id) REFERENCES baseline_messages(id)
                );

                CREATE INDEX IF NOT EXISTS idx_segments_anchor_ts ON baseline_segments(anchor_timestamp_unix);
                CREATE INDEX IF NOT EXISTS idx_segments_range ON baseline_segments(start_msg_id, end_msg_id);

                CREATE TABLE IF NOT EXISTS segment_embeddings (
                    segment_id INTEGER PRIMARY KEY,
                    persona_key TEXT NOT NULL DEFAULT 'dxa',
                    model TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    text_source TEXT NOT NULL DEFAULT 'anchor_text',
                    vector_blob BLOB NOT NULL,
                    norm REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(segment_id) REFERENCES baseline_segments(id)
                );

                CREATE INDEX IF NOT EXISTS idx_segment_embeddings_model_dim ON segment_embeddings(model, dim);

                CREATE TABLE IF NOT EXISTS online_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    message_type TEXT NOT NULL DEFAULT 'text',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    feedback_score INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_online_conv ON online_conversations(conversation_id, id);
                CREATE INDEX IF NOT EXISTS idx_online_created ON online_conversations(created_at);

                CREATE TABLE IF NOT EXISTS generated_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    user_message_id INTEGER NOT NULL,
                    candidate_json TEXT NOT NULL,
                    score REAL NOT NULL,
                    selected INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feedback_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    message_ids_json TEXT NOT NULL,
                    comment TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_time_state (
                    conversation_id TEXT PRIMARY KEY,
                    persona_key TEXT NOT NULL DEFAULT 'dxa',
                    last_user_at TEXT,
                    last_assistant_at TEXT,
                    last_time_ack_at TEXT,
                    last_topic_summary TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_time_state_updated ON conversation_time_state(updated_at);

                CREATE TABLE IF NOT EXISTS conversation_followups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    persona_key TEXT NOT NULL DEFAULT 'dxa',
                    source_message_id INTEGER NOT NULL DEFAULT 0,
                    owner_role TEXT NOT NULL DEFAULT 'assistant',
                    topic TEXT NOT NULL DEFAULT '',
                    due_at TEXT,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_followups_conv_status ON conversation_followups(conversation_id, status, due_at);

                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_type TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS persona_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_key TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                """
            )

            # Schema migration for older DBs.
            base_cols = {r["name"] for r in conn.execute("PRAGMA table_info(baseline_messages)").fetchall()}
            if "persona_key" not in base_cols:
                conn.execute(
                    "ALTER TABLE baseline_messages ADD COLUMN persona_key TEXT NOT NULL DEFAULT 'dxa'"
                )

            seg_cols = {r["name"] for r in conn.execute("PRAGMA table_info(baseline_segments)").fetchall()}
            if "persona_key" not in seg_cols:
                conn.execute(
                    "ALTER TABLE baseline_segments ADD COLUMN persona_key TEXT NOT NULL DEFAULT 'dxa'"
                )

            cols = {r["name"] for r in conn.execute("PRAGMA table_info(segment_embeddings)").fetchall()}
            if "text_source" not in cols:
                conn.execute(
                    "ALTER TABLE segment_embeddings ADD COLUMN text_source TEXT NOT NULL DEFAULT 'anchor_text'"
                )
            if "persona_key" not in cols:
                conn.execute(
                    "ALTER TABLE segment_embeddings ADD COLUMN persona_key TEXT NOT NULL DEFAULT 'dxa'"
                )

            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_baseline_persona ON baseline_messages(persona_key);
                CREATE INDEX IF NOT EXISTS idx_segments_persona ON baseline_segments(persona_key);
                CREATE INDEX IF NOT EXISTS idx_segment_embeddings_persona ON segment_embeddings(persona_key);
                """
            )

            conn.executescript(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS baseline_messages_fts
                USING fts5(content, role, sender, content='baseline_messages', content_rowid='id');

                CREATE VIRTUAL TABLE IF NOT EXISTS baseline_segments_fts
                USING fts5(anchor_text, segment_text, content='baseline_segments', content_rowid='id');

                CREATE VIRTUAL TABLE IF NOT EXISTS online_conversations_fts
                USING fts5(content, role, conversation_id, content='online_conversations', content_rowid='id');
                """
            )

            conn.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS baseline_ai AFTER INSERT ON baseline_messages BEGIN
                  INSERT INTO baseline_messages_fts(rowid, content, role, sender)
                  VALUES (new.id, new.content, new.role, new.sender);
                END;
                CREATE TRIGGER IF NOT EXISTS baseline_ad AFTER DELETE ON baseline_messages BEGIN
                  INSERT INTO baseline_messages_fts(baseline_messages_fts, rowid, content, role, sender)
                  VALUES('delete', old.id, old.content, old.role, old.sender);
                END;
                CREATE TRIGGER IF NOT EXISTS baseline_au AFTER UPDATE ON baseline_messages BEGIN
                  INSERT INTO baseline_messages_fts(baseline_messages_fts, rowid, content, role, sender)
                  VALUES('delete', old.id, old.content, old.role, old.sender);
                  INSERT INTO baseline_messages_fts(rowid, content, role, sender)
                  VALUES (new.id, new.content, new.role, new.sender);
                END;

                CREATE TRIGGER IF NOT EXISTS seg_ai AFTER INSERT ON baseline_segments BEGIN
                  INSERT INTO baseline_segments_fts(rowid, anchor_text, segment_text)
                  VALUES (new.id, new.anchor_text, new.segment_text);
                END;
                CREATE TRIGGER IF NOT EXISTS seg_ad AFTER DELETE ON baseline_segments BEGIN
                  INSERT INTO baseline_segments_fts(baseline_segments_fts, rowid, anchor_text, segment_text)
                  VALUES('delete', old.id, old.anchor_text, old.segment_text);
                END;
                CREATE TRIGGER IF NOT EXISTS seg_au AFTER UPDATE ON baseline_segments BEGIN
                  INSERT INTO baseline_segments_fts(baseline_segments_fts, rowid, anchor_text, segment_text)
                  VALUES('delete', old.id, old.anchor_text, old.segment_text);
                  INSERT INTO baseline_segments_fts(rowid, anchor_text, segment_text)
                  VALUES (new.id, new.anchor_text, new.segment_text);
                END;

                CREATE TRIGGER IF NOT EXISTS online_ai AFTER INSERT ON online_conversations BEGIN
                  INSERT INTO online_conversations_fts(rowid, content, role, conversation_id)
                  VALUES (new.id, new.content, new.role, new.conversation_id);
                END;
                CREATE TRIGGER IF NOT EXISTS online_ad AFTER DELETE ON online_conversations BEGIN
                  INSERT INTO online_conversations_fts(online_conversations_fts, rowid, content, role, conversation_id)
                  VALUES('delete', old.id, old.content, old.role, old.conversation_id);
                END;
                CREATE TRIGGER IF NOT EXISTS online_au AFTER UPDATE ON online_conversations BEGIN
                  INSERT INTO online_conversations_fts(online_conversations_fts, rowid, content, role, conversation_id)
                  VALUES('delete', old.id, old.content, old.role, old.conversation_id);
                  INSERT INTO online_conversations_fts(rowid, content, role, conversation_id)
                  VALUES (new.id, new.content, new.role, new.conversation_id);
                END;
                """
            )

    def get_profile(self, profile_type: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles WHERE profile_type = ?",
                (profile_type,),
            ).fetchone()
        if not row:
            return None
        row["payload"] = json.loads(row["payload_json"])
        return row

    def upsert_profile(self, profile_type: str, payload: dict[str, Any], bump_version: bool = False) -> None:
        now = utc_now_iso()
        with self.connect() as conn:
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
            else:
                conn.execute(
                    """
                    INSERT INTO profiles(profile_type, payload_json, version, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (profile_type, json.dumps(payload, ensure_ascii=False), 1, now),
                )

    def get_persona_profile(self, profile_key: str = "default") -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM persona_profiles WHERE profile_key = ?",
                (profile_key,),
            ).fetchone()
        if not row:
            return None
        row["payload"] = json.loads(row["payload_json"])
        return row

    def upsert_persona_profile(
        self,
        payload: dict[str, Any],
        *,
        profile_key: str = "default",
        bump_version: bool = False,
    ) -> None:
        now = utc_now_iso()
        with self.connect() as conn:
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
            else:
                conn.execute(
                    """
                    INSERT INTO persona_profiles(profile_key, payload_json, version, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (profile_key, json.dumps(payload, ensure_ascii=False), 1, now),
                )


db = Database(settings.sqlite_path)
