from __future__ import annotations

from fastapi import APIRouter, Query

from ..config import settings
from ..db import db
from ..schemas import HealthResponse, SearchResponse, SearchResultDTO
from ..services.gemini_client import get_gemini_client
from ..services.retrieval import retrieval_service
from ..services.semantic_index import semantic_index_service
from ..services.memory import memory_service
from ..services.persona_routing import resolve_persona_key_from_conversation_id

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        env=settings.app_env,
        model_pro=settings.gemini_pro_model,
        model_flash=settings.gemini_flash_model,
    )


@router.get("/profiles")
def profiles(persona_key: str = "", conversation_id: str = "") -> dict:
    key = (persona_key or "").strip()
    if not key and conversation_id:
        key = resolve_persona_key_from_conversation_id(conversation_id)
    if not key:
        key = settings.dxa_persona_key
    style = db.get_profile(f"style:{key}") or (db.get_profile("style") if key == settings.dxa_persona_key else None)
    pref = db.get_profile(f"preference:{key}") or (db.get_profile("preference") if key == settings.dxa_persona_key else None)
    persona = db.get_persona_profile(key) or (db.get_persona_profile("default") if key == settings.dxa_persona_key else None)
    return {
        "persona_key": key,
        "style_version": style["version"] if style else 0,
        "preference_version": pref["version"] if pref else 0,
        "persona_version": persona["version"] if persona else 0,
        "nickname_policy": (pref or {}).get("payload", {}).get("nickname", {}),
        "persona": (persona or {}).get("payload", {}),
        "time_state": memory_service.get_time_state(conversation_id) if conversation_id else None,
        "open_followups": memory_service.list_open_followups(conversation_id, limit=8) if conversation_id else [],
    }


@router.get("/models")
def models() -> dict:
    try:
        names = get_gemini_client().list_models()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "models": []}
    return {"ok": True, "models": names[:300]}


@router.get("/rag/preview")
def rag_preview(q: str, top_k: int = 3, persona_key: str = "", conversation_id: str = "") -> dict:
    top_k = max(1, min(top_k, 12))
    key = (persona_key or "").strip()
    if not key and conversation_id:
        key = resolve_persona_key_from_conversation_id(conversation_id)
    if not key:
        key = settings.dxa_persona_key
    segments = retrieval_service.retrieve_similar_segments(
        q,
        top_k_hits=top_k,
        window_before=settings.segment_window_before,
        window_after=settings.segment_window_after,
        persona_key=key,
    )
    return {
        "query": q,
        "persona_key": key,
        "count": len(segments),
        "segments": segments,
    }


@router.get("/rag/index/status")
def rag_index_status() -> dict:
    return semantic_index_service.get_status()


@router.post("/rag/index/build")
def rag_index_build(
    limit: int = Query(default=0, ge=0),
    batch_size: int = Query(default=24, ge=1, le=256),
    export_only: bool = Query(default=False),
) -> dict:
    if export_only:
        return {
            "ok": True,
            "result": semantic_index_service.export_dense_index(),
            "status": semantic_index_service.get_status(),
        }

    result = semantic_index_service.build_embeddings(
        limit=limit,
        batch_size=batch_size,
        refresh_dense=True,
    )
    return {"ok": True, "result": result, "status": semantic_index_service.get_status()}


@router.get("/search", response_model=SearchResponse)
def search(q: str = "") -> SearchResponse:
    rows = memory_service.search_messages(q, limit=50)
    results = [
        SearchResultDTO(
            id=int(r["id"]),
            conversation_id=str(r["conversation_id"]),
            role=str(r["role"]),
            content=str(r["content"]),
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]
    return SearchResponse(query=q, results=results)
