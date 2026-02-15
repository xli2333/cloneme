# Memory Strategy (Final)

## Goals
- Keep replies grounded in the current real-world context and avoid drift.
- Keep semantic RAG as the core relevance engine.
- Keep long-term persona stable and consistent with historical chat behavior.

## Priority
1. Short-term context grounding: do not go off-topic.
2. Mid-term RAG semantics and style carry-over: preserve meaning and expression quality.
3. Long-term persona consistency: preserve identity and relationship anchors.

## Short-Term Layer
- Build a context frame from recent turns plus current user message.
- Score topical drift as a soft penalty (`offtopic_score`), not a hard reject.
- Use three-stage handling:
  - low drift: direct output
  - medium drift: repair pass (minimal rewrite)
  - high drift: persona fallback

## Mid-Term Layer (RAG)
- Keep current hybrid lexical + semantic retrieval flow.
- Return longer raw segments by:
  - dynamic context window expansion for complex queries
  - prompt-size guard (`RAG_MAX_SEGMENT_CHARS`) to prevent overflow
- Preserve original segment scoring and ranking behavior.

## Long-Term Layer (Persona)
- Store explicit persona profile in `persona_profiles`.
- Split persona into:
  - `core_persona` (stable identity/relationship/anchors/guardrails)
  - `adaptive_persona` (slowly evolving speech traits)
- Inject only `persona_brief` into prompts; keep full persona for scoring.
- Add persona consistency score and penalty in reranking.
- Update persona via candidate promotion:
  - feedback accumulates into `persona_candidate`
  - only promote when sample threshold and phrase-frequency threshold are met
  - reset candidate bucket after promotion
- Use TTL cache for persona reads in generation to avoid per-turn full persona reload.

## Scoring and Selection
- Candidate score combines:
  - semantic relevance
  - style alignment
  - segment alignment
  - online-context alignment
  - persona consistency
- Penalties:
  - copy penalty
  - short-term drift penalty
  - persona mismatch penalty
- Selection pipeline:
  - score and rerank
  - optional critic choice
  - repair pass before fallback

## Fallback Policy
- Use persona-aware fallback only as last resort.
- Fallback text explicitly acknowledges the user’s current point.
- Avoid generic robotic fallback lines.

## Observability
- Debug output includes:
  - `final_path` (`direct|repair|fallback`)
  - `repair_applied`
  - `fallback_reason`
  - `offtopic_score`
  - `persona_score`
  - `memory_contribution`
  - `rag_chars`

## Runtime Controls
- `ENABLE_OFFTOPIC_PENALTY`
- `ENABLE_REPAIR_PASS`
- `ENABLE_PERSONA_GUARD`
- `OFFTOPIC_PENALTY_WEIGHT`
- `REPAIR_THRESHOLD_LOW/MID/HIGH`
- `RAG_MAX_SEGMENT_CHARS`
- `RAG_DYNAMIC_WINDOW_ENABLED`
- `RAG_DYNAMIC_WINDOW_EXTRA`
