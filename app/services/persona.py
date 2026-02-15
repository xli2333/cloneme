from __future__ import annotations

from typing import Any


def normalize_persona_payload(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    if "core_persona" in raw or "adaptive_persona" in raw:
        core = dict(raw.get("core_persona") or {})
        adaptive = dict(raw.get("adaptive_persona") or {})
    else:
        core = {
            "identity": dict(raw.get("identity") or {}),
            "relationship": dict(raw.get("relationship") or {}),
            "anchors": dict(raw.get("anchors") or {}),
            "guardrails": dict(raw.get("guardrails") or {}),
            "locked": bool(raw.get("locked", True)),
        }
        adaptive = {
            "speech_traits": dict(raw.get("speech_traits") or {}),
            "updated_from_feedback": bool(raw.get("updated_from_feedback", False)),
        }

    core.setdefault("identity", {})
    core.setdefault("relationship", {})
    core.setdefault("anchors", {})
    core.setdefault("guardrails", {})
    core.setdefault("locked", True)
    adaptive.setdefault("speech_traits", {})
    adaptive.setdefault("updated_from_feedback", False)

    return {
        "version_note": str(raw.get("version_note") or "persona"),
        "core_persona": core,
        "adaptive_persona": adaptive,
    }


def flatten_persona(raw: dict[str, Any] | None) -> dict[str, Any]:
    persona = normalize_persona_payload(raw)
    core = persona.get("core_persona", {})
    adaptive = persona.get("adaptive_persona", {})
    speech_traits = dict(adaptive.get("speech_traits") or {})
    return {
        "identity": dict(core.get("identity") or {}),
        "relationship": dict(core.get("relationship") or {}),
        "anchors": dict(core.get("anchors") or {}),
        "guardrails": dict(core.get("guardrails") or {}),
        "locked": bool(core.get("locked", True)),
        "speech_traits": speech_traits,
    }


def persona_brief(raw: dict[str, Any] | None, phrase_limit: int = 16) -> dict[str, Any]:
    flat = flatten_persona(raw)
    phrases = [str(x) for x in flat.get("speech_traits", {}).get("top_phrases", []) if str(x).strip()]
    brief = {
        "identity": flat.get("identity", {}),
        "relationship": {
            "strict_nickname": flat.get("relationship", {}).get("strict_nickname", ""),
            "forbidden_nicknames": list(flat.get("relationship", {}).get("forbidden_nicknames", [])),
        },
        "anchors": {
            "style": flat.get("anchors", {}).get("style", ""),
            "behavior": flat.get("anchors", {}).get("behavior", ""),
            "risk": flat.get("anchors", {}).get("risk", ""),
        },
        "speech_traits": {
            "avg_len": flat.get("speech_traits", {}).get("avg_len", 0.0),
            "run_avg": flat.get("speech_traits", {}).get("run_avg", 0.0),
            "top_phrases": phrases[: max(1, int(phrase_limit))],
        },
    }
    return brief


def merge_phrase_scores(
    existing: list[str],
    candidate_scores: dict[str, int],
    *,
    limit: int,
    min_freq: int,
    forbidden: list[str] | None = None,
) -> list[str]:
    forbidden = forbidden or []
    merged: list[str] = [str(x).strip() for x in existing if str(x).strip()]
    blocked = set(str(x).strip() for x in forbidden if str(x).strip())
    for phrase, score in sorted(candidate_scores.items(), key=lambda kv: (-int(kv[1]), kv[0])):
        text = str(phrase).strip()
        if not text:
            continue
        if int(score) < int(min_freq):
            continue
        if any(b and b in text for b in blocked):
            continue
        if text in merged:
            continue
        merged.append(text)
        if len(merged) >= int(limit):
            break
    return merged[: int(limit)]
