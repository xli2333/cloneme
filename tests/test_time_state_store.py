from __future__ import annotations

import unittest
from uuid import uuid4

from app.db import db
from app.services.memory import memory_service


class TimeStateStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_schema()

    def test_upsert_time_state_should_merge_fields(self) -> None:
        cid = f"test-time-{uuid4().hex}"
        memory_service.upsert_time_state(
            conversation_id=cid,
            persona_key="friends",
            last_user_at="2026-02-17T00:00:00+00:00",
        )
        memory_service.upsert_time_state(
            conversation_id=cid,
            persona_key="friends",
            last_assistant_at="2026-02-17T00:00:05+00:00",
        )
        row = memory_service.get_time_state(cid)
        self.assertIsNotNone(row)
        self.assertEqual(str(row.get("persona_key")), "friends")
        self.assertEqual(str(row.get("last_user_at")), "2026-02-17T00:00:00+00:00")
        self.assertEqual(str(row.get("last_assistant_at")), "2026-02-17T00:00:05+00:00")

    def test_followup_extraction_and_list(self) -> None:
        cid = f"test-followup-{uuid4().hex}"
        memory_service.maybe_add_followup(
            conversation_id=cid,
            persona_key="dxa",
            source_message_id=1,
            owner_role="assistant",
            content="这个我明天发你详细版",
        )
        rows = memory_service.list_open_followups(cid, limit=5)
        self.assertTrue(rows)
        self.assertEqual(str(rows[0].get("persona_key")), "dxa")


if __name__ == "__main__":
    unittest.main()
