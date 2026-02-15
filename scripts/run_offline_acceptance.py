from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.generation import GenerationService


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _pct(hit: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * hit / total, 2)


def evaluate() -> dict:
    svc = GenerationService()
    pref = {
        "weights": {
            "semantic": 0.45,
            "style": 0.22,
            "relation": 0.12,
            "recency": 0.08,
            "online_memory": 0.13,
        },
        "tone": {"laugh_ratio_target": 0.1},
        "multi_bubble": {"default_count": 2},
    }
    style = {"avg_len": 8, "median_len": 8, "run_avg": 2.0, "laugh_ratio": 0.1}
    persona = {
        "relationship": {"strict_nickname": "宝贝", "forbidden_nicknames": ["老婆", "宝宝"]},
        "speech_traits": {"avg_len": 8, "top_phrases": ["我在", "先接住你"]},
    }

    short_rows = _read_jsonl(Path("runtime/eval_short_term.jsonl"))
    persona_rows = _read_jsonl(Path("runtime/eval_persona.jsonl"))
    semantic_rows = _read_jsonl(Path("runtime/eval_rag_semantic.jsonl"))

    short_base_hit = 0
    short_final_hit = 0
    for row in short_rows:
        user = str(row["user_message"])
        on_topic = [str(row["on_topic"])]
        off_topic = [str(row["off_topic"])]
        frame = dict(row.get("frame", {}))
        ctx = {"frame": frame, "online_block": [], "segments": []}

        rel_on = svc._relevance_score(user, on_topic)
        rel_off = svc._relevance_score(user, off_topic)
        style_on = svc._style_score(on_topic, style, pref)
        style_off = svc._style_score(off_topic, style, pref)
        flow_on = svc._conversation_flow_score(user, on_topic, frame)
        flow_off = svc._conversation_flow_score(user, off_topic, frame)
        seg_on = svc._segment_alignment_score(on_topic, ctx)
        seg_off = svc._segment_alignment_score(off_topic, ctx)
        ctx_on = svc._context_score(on_topic, ctx)
        ctx_off = svc._context_score(off_topic, ctx)
        copy_on = svc._copy_penalty(on_topic, ctx)
        copy_off = svc._copy_penalty(off_topic, ctx)
        echo_on = svc._echo_penalty(user, on_topic)
        echo_off = svc._echo_penalty(user, off_topic)
        offtopic_on = svc._offtopic_score(user, on_topic, frame)
        offtopic_off = svc._offtopic_score(user, off_topic, frame)
        persona_on = svc._persona_consistency_score(on_topic, persona)
        persona_off = svc._persona_consistency_score(off_topic, persona)

        base_on = max(0.0, min(1.0, 0.52 * rel_on + 0.24 * style_on + 0.14 * seg_on + 0.10 * ctx_on - copy_on))
        base_off = max(0.0, min(1.0, 0.52 * rel_off + 0.24 * style_off + 0.14 * seg_off + 0.10 * ctx_off - copy_off))
        final_on = svc._weighted_total(rel_on, style_on, flow_on, seg_on, ctx_on, persona_on, copy_on, echo_on, offtopic_on, pref)
        final_off = svc._weighted_total(rel_off, style_off, flow_off, seg_off, ctx_off, persona_off, copy_off, echo_off, offtopic_off, pref)

        if base_on > base_off:
            short_base_hit += 1
        if final_on > final_off:
            short_final_hit += 1

    persona_base_hit = 0
    persona_final_hit = 0
    for row in persona_rows:
        safe = [str(row["safe"])]
        bad = [str(row["violate"])]
        p = dict(row.get("persona", persona))
        # Baseline had no persona guard; it can be biased by style-only signals.
        base_safe = svc._style_score(safe, style, pref)
        base_bad = svc._style_score(bad, style, pref)
        final_safe = svc._persona_consistency_score(safe, p)
        final_bad = svc._persona_consistency_score(bad, p)
        if base_safe > base_bad:
            persona_base_hit += 1
        if final_safe > final_bad:
            persona_final_hit += 1

    semantic_base_hit = 0
    semantic_final_hit = 0
    for row in semantic_rows:
        user = str(row["user_message"])
        rel = svc._relevance_score(user, [str(row["relevant"])])
        irr = svc._relevance_score(user, [str(row["irrelevant"])])
        if rel > irr:
            semantic_base_hit += 1
            semantic_final_hit += 1

    return {
        "short_term": {
            "total": len(short_rows),
            "baseline_hit": short_base_hit,
            "final_hit": short_final_hit,
            "baseline_rate": _pct(short_base_hit, len(short_rows)),
            "final_rate": _pct(short_final_hit, len(short_rows)),
        },
        "persona": {
            "total": len(persona_rows),
            "baseline_hit": persona_base_hit,
            "final_hit": persona_final_hit,
            "baseline_rate": _pct(persona_base_hit, len(persona_rows)),
            "final_rate": _pct(persona_final_hit, len(persona_rows)),
        },
        "semantic": {
            "total": len(semantic_rows),
            "baseline_hit": semantic_base_hit,
            "final_hit": semantic_final_hit,
            "baseline_rate": _pct(semantic_base_hit, len(semantic_rows)),
            "final_rate": _pct(semantic_final_hit, len(semantic_rows)),
        },
    }


def write_reports(metrics: dict) -> None:
    baseline = [
        "# Baseline Metrics",
        "",
        f"- short_term_on_topic_rate: {metrics['short_term']['baseline_rate']}% ({metrics['short_term']['baseline_hit']}/{metrics['short_term']['total']})",
        f"- persona_consistency_rate: {metrics['persona']['baseline_rate']}% ({metrics['persona']['baseline_hit']}/{metrics['persona']['total']})",
        f"- semantic_discrimination_rate: {metrics['semantic']['baseline_rate']}% ({metrics['semantic']['baseline_hit']}/{metrics['semantic']['total']})",
    ]
    final = [
        "# Final Metrics",
        "",
        f"- short_term_on_topic_rate: {metrics['short_term']['final_rate']}% ({metrics['short_term']['final_hit']}/{metrics['short_term']['total']})",
        f"- persona_consistency_rate: {metrics['persona']['final_rate']}% ({metrics['persona']['final_hit']}/{metrics['persona']['total']})",
        f"- semantic_discrimination_rate: {metrics['semantic']['final_rate']}% ({metrics['semantic']['final_hit']}/{metrics['semantic']['total']})",
    ]
    Path("reports").mkdir(parents=True, exist_ok=True)
    Path("reports/baseline_metrics.md").write_text("\n".join(baseline), encoding="utf-8")
    Path("reports/final_metrics.md").write_text("\n".join(final), encoding="utf-8")


def main() -> None:
    metrics = evaluate()
    write_reports(metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
