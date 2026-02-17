from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np

from ..config import settings
from ..db import db, utc_now_iso
from .gemini_client import get_gemini_client

logger = logging.getLogger("doppelganger.semantic_index")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_vec(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm <= 0:
        return vec
    return vec / norm


def _blob_to_vec(blob: bytes, dim: int) -> np.ndarray:
    arr = np.frombuffer(blob, dtype=np.float32)
    if arr.size != dim:
        raise ValueError(f"embedding blob dim mismatch expected={dim} actual={arr.size}")
    return arr


class SemanticIndexService:
    def __init__(self) -> None:
        self._ids: np.ndarray | None = None
        self._vectors: np.ndarray | None = None
        self._id_to_pos: dict[int, int] = {}
        self._segment_persona_map: dict[int, str] = {}
        self._persona_to_positions: dict[str, np.ndarray] = {}
        self._loaded_signature: tuple[float, float] | None = None
        self._query_cache: dict[str, np.ndarray] = {}

    @property
    def _source(self) -> str:
        src = settings.gemini_embedding_text_source.strip().lower()
        return src if src in {"anchor_text", "segment_text"} else "segment_text"

    def _embed_query(self, query: str) -> np.ndarray:
        key = query.strip()
        if key in self._query_cache:
            return self._query_cache[key]

        client = get_gemini_client()
        vec = client.embed_texts(
            [key],
            model=settings.gemini_embedding_model,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=settings.gemini_embedding_dim,
        )[0]
        arr = _normalize_vec(np.asarray(vec, dtype=np.float32))

        self._query_cache[key] = arr
        if len(self._query_cache) > 256:
            self._query_cache.pop(next(iter(self._query_cache)))
        return arr

    def _fetch_segment_texts(self, segment_ids: list[int]) -> dict[int, str]:
        if not segment_ids:
            return {}
        col = "segment_text" if self._source == "segment_text" else "anchor_text"
        with db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, {col} AS text
                FROM baseline_segments
                WHERE id IN ({','.join('?' for _ in segment_ids)})
                """,
                segment_ids,
            ).fetchall()
        return {int(r["id"]): str(r["text"] or "") for r in rows}

    def _fetch_segment_persona_keys(self, segment_ids: list[int]) -> dict[int, str]:
        if not segment_ids:
            return {}
        out: dict[int, str] = {}
        chunk = 800
        with db.connect() as conn:
            for i in range(0, len(segment_ids), chunk):
                part = segment_ids[i : i + chunk]
                rows = conn.execute(
                    f"""
                    SELECT id, persona_key
                    FROM baseline_segments
                    WHERE id IN ({','.join('?' for _ in part)})
                    """,
                    part,
                ).fetchall()
                for row in rows:
                    out[int(row["id"])] = str(row.get("persona_key") or settings.dxa_persona_key)
        return out

    def get_status(self) -> dict[str, Any]:
        with db.connect() as conn:
            seg_row = conn.execute("SELECT COUNT(*) AS c FROM baseline_segments").fetchone()
            emb_row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM segment_embeddings
                WHERE model = ? AND dim = ? AND text_source = ?
                """,
                (settings.gemini_embedding_model, settings.gemini_embedding_dim, self._source),
            ).fetchone()

        ids_path = settings.segment_ids_path
        vecs_path = settings.segment_vectors_path
        meta_path = settings.segment_index_meta_path
        meta_payload: dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta_payload = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta_payload = {}

        return {
            "segments": int(seg_row["c"]) if seg_row else 0,
            "embeddings": int(emb_row["c"]) if emb_row else 0,
            "embedding_model": settings.gemini_embedding_model,
            "embedding_dim": settings.gemini_embedding_dim,
            "embedding_text_source": self._source,
            "ids_file": str(ids_path),
            "vectors_file": str(vecs_path),
            "meta_file": str(meta_path),
            "ids_file_exists": ids_path.exists(),
            "vectors_file_exists": vecs_path.exists(),
            "meta": meta_payload,
            "dense_loaded": self._ids is not None and self._vectors is not None,
        }

    def ensure_embeddings_for_segments(
        self,
        segment_ids: list[int],
        *,
        batch_size: int | None = None,
        max_items: int = 0,
        refresh_dense: bool = False,
    ) -> dict[str, Any]:
        segment_ids = [int(x) for x in segment_ids if int(x) > 0]
        if not segment_ids:
            return {"written": 0, "checked": 0}

        with db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT segment_id, model, dim, text_source
                FROM segment_embeddings
                WHERE segment_id IN ({','.join('?' for _ in segment_ids)})
                """,
                segment_ids,
            ).fetchall()

        ok_ids = {
            int(r["segment_id"])
            for r in rows
            if str(r.get("model")) == settings.gemini_embedding_model
            and int(r.get("dim") or 0) == settings.gemini_embedding_dim
            and str(r.get("text_source") or "anchor_text") == self._source
        }

        missing = [sid for sid in segment_ids if sid not in ok_ids]
        if max_items > 0:
            missing = missing[:max_items]
        if not missing:
            return {"written": 0, "checked": len(segment_ids)}

        text_map = self._fetch_segment_texts(missing)
        missing = [sid for sid in missing if sid in text_map and text_map[sid].strip()]
        if not missing:
            return {"written": 0, "checked": len(segment_ids)}
        persona_map = self._fetch_segment_persona_keys(missing)

        bs = max(1, int(batch_size or settings.embedding_batch_size))
        client = get_gemini_client()
        written = 0

        for i in range(0, len(missing), bs):
            chunk_ids = missing[i : i + bs]
            texts = [text_map[sid] for sid in chunk_ids]
            vecs = client.embed_texts(
                texts,
                model=settings.gemini_embedding_model,
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=settings.gemini_embedding_dim,
            )

            now = utc_now_iso()
            payloads: list[dict[str, Any]] = []
            for sid, vec in zip(chunk_ids, vecs):
                arr = _normalize_vec(np.asarray(vec, dtype=np.float32))
                payloads.append(
                    {
                        "segment_id": sid,
                        "persona_key": persona_map.get(sid, settings.dxa_persona_key),
                        "model": settings.gemini_embedding_model,
                        "dim": settings.gemini_embedding_dim,
                        "text_source": self._source,
                        "vector_blob": arr.tobytes(),
                        "norm": 1.0,
                        "created_at": now,
                        "updated_at": now,
                    }
                )

            with db.connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO segment_embeddings(segment_id, persona_key, model, dim, text_source, vector_blob, norm, created_at, updated_at)
                    VALUES(:segment_id, :persona_key, :model, :dim, :text_source, :vector_blob, :norm, :created_at, :updated_at)
                    ON CONFLICT(segment_id) DO UPDATE SET
                      persona_key = excluded.persona_key,
                      model = excluded.model,
                      dim = excluded.dim,
                      text_source = excluded.text_source,
                      vector_blob = excluded.vector_blob,
                      norm = excluded.norm,
                      updated_at = excluded.updated_at
                    """,
                    payloads,
                )
            written += len(payloads)

        if refresh_dense and written > 0:
            self.export_dense_index()

        logger.info(
            "semantic_autofill_embeddings checked=%d missing=%d written=%d source=%s",
            len(segment_ids),
            len(missing),
            written,
            self._source,
        )
        return {"written": written, "checked": len(segment_ids)}

    def build_embeddings(
        self,
        *,
        limit: int = 0,
        batch_size: int | None = None,
        refresh_dense: bool = True,
    ) -> dict[str, Any]:
        bs = max(1, int(batch_size or settings.embedding_batch_size))
        remaining = int(limit)
        total_written = 0

        while True:
            with db.connect() as conn:
                sql = (
                    """
                    SELECT s.id
                    FROM baseline_segments s
                    LEFT JOIN segment_embeddings e ON e.segment_id = s.id
                    WHERE e.segment_id IS NULL
                       OR e.model != ?
                       OR e.dim != ?
                       OR e.text_source != ?
                       OR e.persona_key != s.persona_key
                    ORDER BY s.id ASC
                    LIMIT ?
                    """
                )
                take = bs if remaining <= 0 else min(bs, remaining)
                rows = conn.execute(
                    sql,
                    (settings.gemini_embedding_model, settings.gemini_embedding_dim, self._source, take),
                ).fetchall()

            if not rows:
                break

            ids = [int(r["id"]) for r in rows]
            result = self.ensure_embeddings_for_segments(ids, batch_size=bs, refresh_dense=False)
            wrote = int(result.get("written", 0))
            total_written += wrote

            logger.info(
                "semantic_embedding_progress requested=%d wrote=%d total_written=%d dim=%d model=%s source=%s",
                len(ids),
                wrote,
                total_written,
                settings.gemini_embedding_dim,
                settings.gemini_embedding_model,
                self._source,
            )

            if remaining > 0:
                remaining -= len(ids)
                if remaining <= 0:
                    break

        exported = 0
        if refresh_dense:
            exported = self.export_dense_index()["rows"]

        return {
            "written": total_written,
            "exported": exported,
            "model": settings.gemini_embedding_model,
            "dim": settings.gemini_embedding_dim,
            "text_source": self._source,
        }

    def export_dense_index(self) -> dict[str, Any]:
        settings.segment_ids_path.parent.mkdir(parents=True, exist_ok=True)
        settings.segment_vectors_path.parent.mkdir(parents=True, exist_ok=True)
        settings.segment_index_meta_path.parent.mkdir(parents=True, exist_ok=True)

        with db.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM segment_embeddings
                WHERE model = ? AND dim = ? AND text_source = ?
                """,
                (settings.gemini_embedding_model, settings.gemini_embedding_dim, self._source),
            ).fetchone()
            count = int(row["c"]) if row else 0

            ids_mm = np.lib.format.open_memmap(
                settings.segment_ids_path,
                mode="w+",
                dtype=np.int64,
                shape=(count,),
            )
            vecs_mm = np.lib.format.open_memmap(
                settings.segment_vectors_path,
                mode="w+",
                dtype=np.float32,
                shape=(count, settings.gemini_embedding_dim),
            )

            cursor = conn.execute(
                """
                SELECT e.segment_id, e.vector_blob
                FROM segment_embeddings e
                WHERE e.model = ? AND e.dim = ? AND e.text_source = ?
                ORDER BY e.segment_id ASC
                """,
                (settings.gemini_embedding_model, settings.gemini_embedding_dim, self._source),
            )

            i = 0
            for row_item in cursor:
                seg_id = int(row_item["segment_id"])
                vec = _blob_to_vec(row_item["vector_blob"], settings.gemini_embedding_dim)
                ids_mm[i] = seg_id
                vecs_mm[i] = vec
                i += 1

            ids_mm.flush()
            vecs_mm.flush()

        meta = {
            "count": count,
            "dim": settings.gemini_embedding_dim,
            "model": settings.gemini_embedding_model,
            "text_source": self._source,
            "built_at": _now_iso(),
            "ids_file": str(settings.segment_ids_path),
            "vectors_file": str(settings.segment_vectors_path),
        }
        settings.segment_index_meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        self._loaded_signature = None
        self._ids = None
        self._vectors = None
        self._id_to_pos.clear()
        self._segment_persona_map.clear()
        self._persona_to_positions.clear()

        logger.info("semantic_dense_export_done count=%d dim=%d source=%s", count, settings.gemini_embedding_dim, self._source)
        return {"rows": count, "meta": meta}

    def ensure_dense_loaded(self, *, force: bool = False) -> bool:
        if not settings.semantic_use_dense_index:
            return False
        if not settings.segment_ids_path.exists() or not settings.segment_vectors_path.exists():
            return False

        sig = (
            settings.segment_ids_path.stat().st_mtime,
            settings.segment_vectors_path.stat().st_mtime,
        )
        if not force and self._loaded_signature == sig and self._ids is not None and self._vectors is not None:
            return True

        self._ids = np.load(settings.segment_ids_path, mmap_mode="r")
        self._vectors = np.load(settings.segment_vectors_path, mmap_mode="r")
        if self._vectors.ndim != 2 or self._vectors.shape[1] != settings.gemini_embedding_dim:
            raise RuntimeError(
                f"dense index dim mismatch expected={settings.gemini_embedding_dim} actual={self._vectors.shape}"
            )

        if settings.segment_index_meta_path.exists():
            try:
                meta = json.loads(settings.segment_index_meta_path.read_text(encoding="utf-8"))
                meta_source = str(meta.get("text_source", "") or "")
                if meta_source != self._source:
                    logger.warning(
                        "dense_meta_source_mismatch expected=%s actual=%s; skip dense and use db vectors",
                        self._source,
                        meta_source or "<missing>",
                    )
                    self._ids = None
                    self._vectors = None
                    self._id_to_pos = {}
                    self._segment_persona_map = {}
                    self._persona_to_positions = {}
                    self._loaded_signature = None
                    return False
            except Exception:
                pass

        self._id_to_pos = {int(seg_id): idx for idx, seg_id in enumerate(self._ids.tolist())}
        seg_ids = [int(x) for x in self._ids.tolist()]
        self._segment_persona_map = self._fetch_segment_persona_keys(seg_ids)
        persona_pos: dict[str, list[int]] = {}
        for sid, pos in self._id_to_pos.items():
            key = self._segment_persona_map.get(sid, settings.dxa_persona_key)
            persona_pos.setdefault(key, []).append(pos)
        self._persona_to_positions = {
            key: np.asarray(sorted(positions), dtype=np.int64)
            for key, positions in persona_pos.items()
        }
        self._loaded_signature = sig
        logger.info(
            "semantic_dense_loaded rows=%d dim=%d source=%s personas=%s",
            int(self._vectors.shape[0]),
            int(self._vectors.shape[1]),
            self._source,
            sorted(list(self._persona_to_positions.keys())),
        )
        return True

    def search(self, query: str, *, top_k: int, persona_key: str | None = None) -> list[dict[str, Any]]:
        if not query.strip() or top_k <= 0:
            return []
        if not self.ensure_dense_loaded():
            return []
        if self._vectors is None or self._ids is None:
            return []

        qvec = self._embed_query(query)
        scores = self._vectors @ qvec

        if persona_key:
            key = persona_key.strip() or settings.dxa_persona_key
            positions = self._persona_to_positions.get(key)
            if positions is None or positions.size == 0:
                return []
            scoped_scores = scores[positions]
            k = min(int(top_k), int(scoped_scores.shape[0]))
            if k <= 0:
                return []
            idx = np.argpartition(scoped_scores, -k)[-k:]
            idx = idx[np.argsort(scoped_scores[idx])[::-1]]
            chosen_pos = positions[idx]
            return [
                {
                    "segment_id": int(self._ids[pos]),
                    "semantic_score": float(scores[pos]),
                }
                for pos in chosen_pos.tolist()
            ]

        k = min(int(top_k), int(scores.shape[0]))
        if k <= 0:
            return []
        idx = np.argpartition(scores, -k)[-k:]
        idx = idx[np.argsort(scores[idx])[::-1]]

        return [
            {
                "segment_id": int(self._ids[i]),
                "semantic_score": float(scores[i]),
            }
            for i in idx.tolist()
        ]

    def semantic_scores_for_segment_ids(self, query: str, segment_ids: list[int]) -> dict[int, float]:
        if not query.strip() or not segment_ids:
            return {}
        qvec = self._embed_query(query)
        out: dict[int, float] = {}

        loaded = self.ensure_dense_loaded()
        if loaded and self._vectors is not None:
            for sid in segment_ids:
                pos = self._id_to_pos.get(int(sid))
                if pos is None:
                    continue
                out[int(sid)] = float(np.dot(self._vectors[pos], qvec))

        missing = [sid for sid in segment_ids if sid not in out]
        if not missing:
            return out

        with db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT segment_id, vector_blob
                FROM segment_embeddings
                WHERE model = ? AND dim = ? AND text_source = ?
                  AND segment_id IN ({','.join('?' for _ in missing)})
                """,
                [settings.gemini_embedding_model, settings.gemini_embedding_dim, self._source, *missing],
            ).fetchall()

        for row in rows:
            sid = int(row["segment_id"])
            vec = _blob_to_vec(row["vector_blob"], settings.gemini_embedding_dim)
            out[sid] = float(np.dot(vec, qvec))

        return out


semantic_index_service = SemanticIndexService()
