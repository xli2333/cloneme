from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.bootstrap import bootstrap_if_needed
from app.services.semantic_index import semantic_index_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 3072-dim semantic index for Doppelganger RAG")
    parser.add_argument("--limit", type=int, default=0, help="Max segments to embed in this run (0 = all missing)")
    parser.add_argument("--batch-size", type=int, default=24, help="Embedding batch size")
    parser.add_argument("--export-only", action="store_true", help="Only export dense npy files from existing DB embeddings")
    parser.add_argument("--status", action="store_true", help="Print status and exit")
    args = parser.parse_args()

    bootstrap_if_needed()

    if args.status:
        print(json.dumps(semantic_index_service.get_status(), ensure_ascii=False, indent=2))
        return

    if args.export_only:
        result = semantic_index_service.export_dense_index()
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
        return

    result = semantic_index_service.build_embeddings(
        limit=max(0, int(args.limit)),
        batch_size=max(1, int(args.batch_size)),
        refresh_dense=True,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "result": result,
                "status": semantic_index_service.get_status(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
