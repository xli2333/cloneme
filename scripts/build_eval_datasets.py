from __future__ import annotations

import json
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def build_short_term(n: int = 80) -> list[dict]:
    rows: list[dict] = []
    for i in range(n):
        rows.append(
            {
                "id": i + 1,
                "user_message": f"第{i+1}轮：我们今天要不要看电影？",
                "frame": {"focus_terms": ["今天", "看电影", "要不要"], "question_like": True},
                "on_topic": "可以，就看电影。",
                "off_topic": "今天看电影也行哈哈，不过我更想聊旅游攻略。",
            }
        )
    return rows


def build_persona(n: int = 80) -> list[dict]:
    rows: list[dict] = []
    for i in range(n):
        rows.append(
            {
                "id": i + 1,
                "safe": "我在，先接住你这个点。",
                "violate": "老婆哈哈，我马上处理。",
                "persona": {
                    "relationship": {"strict_nickname": "宝贝", "forbidden_nicknames": ["老婆", "宝宝"]},
                    "speech_traits": {"avg_len": 8, "top_phrases": ["我在", "先接住你"]},
                },
            }
        )
    return rows


def build_semantic(n: int = 80) -> list[dict]:
    rows: list[dict] = []
    for i in range(n):
        rows.append(
            {
                "id": i + 1,
                "user_message": "我们今晚看电影吗",
                "relevant": "今晚看电影可以，我这边时间OK。",
                "irrelevant": "明天中午吃什么还没想好。",
            }
        )
    return rows


def main() -> None:
    root = Path("runtime")
    _write_jsonl(root / "eval_short_term.jsonl", build_short_term(80))
    _write_jsonl(root / "eval_persona.jsonl", build_persona(80))
    _write_jsonl(root / "eval_rag_semantic.jsonl", build_semantic(80))
    print("wrote runtime/eval_short_term.jsonl")
    print("wrote runtime/eval_persona.jsonl")
    print("wrote runtime/eval_rag_semantic.jsonl")


if __name__ == "__main__":
    main()
