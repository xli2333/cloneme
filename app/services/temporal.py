from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..config import settings

TIME_ACK_RE = re.compile(r"(好久不见|这么久|隔了.*(天|周)|两天|几天|过了.*(天|周)|回来啦|又来啦|最近怎么样)")
REENTRY_HINT_RE = re.compile(r"(在吗|还在吗|我回来了|我回来啦|回来啦|回来了|重新说|接着说)")


def _timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.app_timezone)
    except Exception:
        return ZoneInfo("UTC")


def parse_iso_datetime(text: str | None) -> datetime | None:
    if not text:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _local_part_of_day(dt_local: datetime) -> str:
    hour = dt_local.hour
    if 0 <= hour < 6:
        return "凌晨"
    if 6 <= hour < 11:
        return "早上"
    if 11 <= hour < 14:
        return "中午"
    if 14 <= hour < 18:
        return "下午"
    return "晚上"


def _gap_bucket(gap_seconds: int | None) -> str:
    if gap_seconds is None:
        return "unknown"
    if gap_seconds < max(0, int(settings.temporal_gap_recent_seconds)):
        return "immediate"
    if gap_seconds < max(int(settings.temporal_gap_recent_seconds), int(settings.temporal_gap_same_day_seconds)):
        return "same_day"
    if gap_seconds < max(int(settings.temporal_gap_same_day_seconds), int(settings.temporal_gap_two_days_seconds)):
        return "within_two_days"
    if gap_seconds < max(int(settings.temporal_gap_two_days_seconds), int(settings.temporal_gap_week_seconds)):
        return "within_week"
    return "over_week"


def _safe_gap_seconds(current_dt: datetime | None, previous_dt: datetime | None) -> tuple[int | None, str]:
    if current_dt is None or previous_dt is None:
        return None, "missing_point"
    delta = int((current_dt - previous_dt).total_seconds())
    if delta < 0:
        return 0, "clock_skew_or_out_of_order"
    max_cap = int(timedelta(days=365 * 10).total_seconds())
    if delta > max_cap:
        return max_cap, "gap_capped"
    return delta, "ok"


def build_temporal_context(
    *,
    user_message: str,
    recent_user_rows: list[dict[str, Any]],
    state_row: dict[str, Any] | None,
) -> dict[str, Any]:
    now_utc = datetime.now(UTC)
    now_local = now_utc.astimezone(_timezone())
    current_user_at = parse_iso_datetime(recent_user_rows[0].get("created_at")) if recent_user_rows else now_utc
    previous_user_at = parse_iso_datetime(recent_user_rows[1].get("created_at")) if len(recent_user_rows) >= 2 else None
    if previous_user_at is None and state_row:
        previous_user_at = parse_iso_datetime(state_row.get("last_user_at"))
        if current_user_at and previous_user_at and previous_user_at >= current_user_at:
            previous_user_at = None
    gap_seconds, gap_state = _safe_gap_seconds(current_user_at, previous_user_at)
    bucket = _gap_bucket(gap_seconds)

    last_ack_at = parse_iso_datetime((state_row or {}).get("last_time_ack_at"))
    ack_cooldown_passed = True
    if last_ack_at is not None:
        cooldown_gap, _ = _safe_gap_seconds(now_utc, last_ack_at)
        ack_cooldown_passed = (cooldown_gap or 0) >= int(settings.temporal_ack_cooldown_seconds)

    reentry_hint = bool(REENTRY_HINT_RE.search(str(user_message)))
    should_time_ack = (
        bucket in {"within_week", "over_week"}
        and ack_cooldown_passed
        and gap_seconds is not None
        and gap_seconds >= int(settings.temporal_gap_two_days_seconds)
    )

    return {
        "now_utc": now_utc.isoformat(),
        "now_local": now_local.isoformat(),
        "part_of_day": _local_part_of_day(now_local),
        "week_type": "weekend" if now_local.weekday() >= 5 else "weekday",
        "current_user_at": current_user_at.isoformat() if current_user_at else "",
        "previous_user_at": previous_user_at.isoformat() if previous_user_at else "",
        "gap_seconds": gap_seconds if gap_seconds is not None else -1,
        "gap_bucket": bucket,
        "gap_state": gap_state,
        "reentry_hint": reentry_hint,
        "ack_cooldown_passed": ack_cooldown_passed,
        "should_time_ack": bool(should_time_ack),
    }


def detect_time_ack_used(bubbles: list[str]) -> bool:
    text = "\n".join([str(x).strip() for x in bubbles if str(x).strip()])
    if not text:
        return False
    return bool(TIME_ACK_RE.search(text))

