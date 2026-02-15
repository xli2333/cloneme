from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db import db

PHRASE_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9~～!?！？]{2,18}")


def _load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("chat data must be a list")
    return [x for x in data if isinstance(x, dict)]


def build_persona(rows: list[dict[str, Any]]) -> dict[str, Any]:
    user_alias = set(settings.user_sender_candidates)
    target_sender = settings.target_sender
    assistant_texts: list[str] = []
    for row in rows:
        sender = str(row.get("sender") or "").strip()
        content = str(row.get("content") or "").strip()
        msg_type = str(row.get("msg_type") or "")
        if not content or msg_type != "1":
            continue
        if sender == target_sender:
            assistant_texts.append(content)

    phrases = Counter()
    for text in assistant_texts:
        for token in PHRASE_RE.findall(text):
            t = token.strip()
            if len(t) < 2:
                continue
            phrases[t] += 1

    return {
        "version_note": "draft_from_long_chat",
        "core_persona": {
            "identity": {
                "name": settings.app_name,
                "target_sender": target_sender,
                "role": "relationship_chat_partner",
            },
            "relationship": {
                "primary_user_aliases": list(user_alias),
                "strict_nickname": settings.strict_nickname,
                "forbidden_nicknames": settings.forbidden_nicknames,
            },
            "anchors": {
                "style": "短句、口语、连发，不跑题",
                "behavior": "先接住当下语境，再扩展表达",
                "risk": "不切换客服腔，不编造无关信息",
            },
            "guardrails": {
                "must_stay_on_context": True,
                "allow_soft_repair": True,
                "fallback_style": "人格化承接，不机械道歉",
            },
            "locked": True,
        },
        "adaptive_persona": {
            "speech_traits": {
                "assistant_sample_count": len(assistant_texts),
                "top_phrases": [k for k, _ in phrases.most_common(120)],
            },
            "updated_from_feedback": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build persona profile draft from long chat data.")
    parser.add_argument("--chat-data", default=str(settings.chat_data_path))
    parser.add_argument("--out", default="runtime/persona_profile_draft.json")
    parser.add_argument("--write-db", action="store_true")
    args = parser.parse_args()

    rows = _load_rows(Path(args.chat_data).resolve())
    persona = build_persona(rows)
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(persona, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote draft: {out_path}")

    if args.write_db:
        db.init_schema()
        db.upsert_persona_profile(persona, bump_version=True)
        row = db.get_persona_profile()
        print(f"upserted persona profile version: {int(row['version']) if row else 0}")


if __name__ == "__main__":
    main()
