# Temporal Awareness (v1)

## Goal
- Make responses aware of elapsed time between user messages.
- Avoid "just talked" tone after long gaps.
- Keep current persona routing behavior unchanged (`dxa` vs `friends`).

## Components
- `conversation_time_state`:
  - `last_user_at`, `last_assistant_at`, `last_time_ack_at`, `last_topic_summary`
- `conversation_followups`:
  - lightweight structured pending items extracted from assistant replies
- `temporal_context`:
  - `gap_seconds`, `gap_bucket`, `part_of_day`, `week_type`, `should_time_ack`, `ack_cooldown_passed`

## Buckets
- `immediate`: `< TEMPORAL_GAP_RECENT_SECONDS`
- `same_day`: `< TEMPORAL_GAP_SAME_DAY_SECONDS`
- `within_two_days`: `< TEMPORAL_GAP_TWO_DAYS_SECONDS`
- `within_week`: `< TEMPORAL_GAP_WEEK_SECONDS`
- `over_week`: `>= TEMPORAL_GAP_WEEK_SECONDS`

## Generation integration
- Prompts include `temporal_context`.
- New scoring: `time_score` in candidate rerank.
- Short gaps penalize "long time no see" style openings.
- Long gaps can allow one light re-entry line.
- Cooldown prevents repetitive time acknowledgements.

## Config
- `APP_TIMEZONE`
- `TEMPORAL_ACK_COOLDOWN_SECONDS`
- `TEMPORAL_GAP_RECENT_SECONDS`
- `TEMPORAL_GAP_SAME_DAY_SECONDS`
- `TEMPORAL_GAP_TWO_DAYS_SECONDS`
- `TEMPORAL_GAP_WEEK_SECONDS`

## Safety
- Handles clock skew / out-of-order timestamps by clamping negative gaps to `0`.
- Caps unrealistic large gaps.
- If temporal state is missing, falls back gracefully.
