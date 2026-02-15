from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import chat as chat_router
from .routers import feedback as feedback_router
from .routers import system as system_router
from .routers import wecom as wecom_router
from .services.bootstrap import bootstrap_if_needed
from .services.semantic_index import semantic_index_service

logger = logging.getLogger("doppelganger")
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title=settings.app_name, version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins or ["http://localhost:5173"],
    allow_origin_regex=settings.cors_allow_origin_regex or None,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router.router)
app.include_router(feedback_router.router)
app.include_router(system_router.router)
app.include_router(wecom_router.router)


@app.on_event("startup")
def on_startup() -> None:
    info = bootstrap_if_needed()
    logger.info("bootstrap finished: %s", info)

    try:
        if settings.semantic_rebuild_on_start:
            logger.info(
                "semantic_rebuild_on_start enabled limit=%d",
                settings.semantic_build_on_start_limit,
            )
            result = semantic_index_service.build_embeddings(
                limit=settings.semantic_build_on_start_limit,
                batch_size=settings.embedding_batch_size,
                refresh_dense=True,
            )
            logger.info("semantic_rebuild_result: %s", result)
        elif settings.semantic_index_auto_refresh:
            status = semantic_index_service.get_status()
            if status.get("embeddings", 0) > 0 and (
                not status.get("ids_file_exists") or not status.get("vectors_file_exists")
            ):
                logger.info("dense index files missing, exporting from db embeddings")
                semantic_index_service.export_dense_index()
            semantic_index_service.ensure_dense_loaded()
            logger.info("semantic_index_status: %s", semantic_index_service.get_status())
    except Exception as exc:
        logger.warning("semantic index warmup failed: %s", exc)


@app.get("/")
def index() -> dict:
    return {
        "name": settings.app_name,
        "env": settings.app_env,
        "status": "ok",
        "docs": "/docs",
        "api_prefix": "/api",
    }
