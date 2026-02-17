from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from app.services.generation import GenerationService
from app.services.temporal import build_temporal_context, detect_time_ack_used


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


class TemporalAwarenessTests(unittest.TestCase):
    def test_gap_bucket_boundaries(self) -> None:
        now = datetime.now(UTC)
        current = _iso(now)
        prev_599 = _iso(now - timedelta(seconds=599))
        prev_600 = _iso(now - timedelta(seconds=600))
        prev_6h = _iso(now - timedelta(seconds=21600))
        prev_2d = _iso(now - timedelta(days=2))

        ctx_599 = build_temporal_context(
            user_message="在吗",
            recent_user_rows=[{"created_at": current}, {"created_at": prev_599}],
            state_row={},
        )
        ctx_600 = build_temporal_context(
            user_message="在吗",
            recent_user_rows=[{"created_at": current}, {"created_at": prev_600}],
            state_row={},
        )
        ctx_6h = build_temporal_context(
            user_message="在吗",
            recent_user_rows=[{"created_at": current}, {"created_at": prev_6h}],
            state_row={},
        )
        ctx_2d = build_temporal_context(
            user_message="在吗",
            recent_user_rows=[{"created_at": current}, {"created_at": prev_2d}],
            state_row={},
        )

        self.assertEqual(ctx_599["gap_bucket"], "immediate")
        self.assertEqual(ctx_600["gap_bucket"], "same_day")
        self.assertEqual(ctx_6h["gap_bucket"], "within_two_days")
        self.assertIn(ctx_2d["gap_bucket"], {"within_week", "over_week"})

    def test_clock_skew_should_be_clamped(self) -> None:
        now = datetime.now(UTC)
        current = _iso(now)
        future_prev = _iso(now + timedelta(seconds=30))
        ctx = build_temporal_context(
            user_message="在吗",
            recent_user_rows=[{"created_at": current}, {"created_at": future_prev}],
            state_row={},
        )
        self.assertEqual(ctx["gap_seconds"], 0)
        self.assertEqual(ctx["gap_state"], "clock_skew_or_out_of_order")

    def test_time_ack_detection(self) -> None:
        self.assertTrue(detect_time_ack_used(["好久不见，先接住你这个点"]))
        self.assertFalse(detect_time_ack_used(["我在，继续说"]))

    def test_time_coherence_scoring(self) -> None:
        svc = GenerationService()
        short_ctx = {"gap_bucket": "immediate", "should_time_ack": False, "ack_cooldown_passed": True}
        long_ctx = {"gap_bucket": "within_week", "should_time_ack": True, "ack_cooldown_passed": True}
        short_ack = svc._time_coherence_score(["好久不见"], short_ctx)
        short_plain = svc._time_coherence_score(["我在，继续"], short_ctx)
        long_ack = svc._time_coherence_score(["好久不见，我在"], long_ctx)
        long_plain = svc._time_coherence_score(["我在，继续"], long_ctx)
        self.assertGreater(short_plain, short_ack)
        self.assertGreater(long_ack, long_plain)


if __name__ == "__main__":
    unittest.main()

