from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..schemas import FeedbackRequest, FeedbackResponse
from ..services.evolution import evolution_service
from ..services.memory import memory_service
from ..services.persona_routing import resolve_persona_key_from_conversation_id

router = APIRouter(prefix="/api", tags=["feedback"])
logger = logging.getLogger("doppelganger.feedback")


@router.post("/feedback", response_model=FeedbackResponse)
def feedback(req: FeedbackRequest) -> FeedbackResponse:
    message_ids = sorted({int(x) for x in req.message_ids if int(x) > 0})
    if not message_ids:
        raise HTTPException(status_code=400, detail="message_ids is empty")

    persona_key = resolve_persona_key_from_conversation_id(req.conversation_id)
    logger.info(
        "api_feedback_in persona=%s conversation=%s message_ids=%s comment=%s",
        persona_key,
        req.conversation_id,
        message_ids,
        req.comment,
    )
    memory_service.add_feedback(
        conversation_id=req.conversation_id,
        message_ids=message_ids,
        comment=req.comment,
    )
    result = evolution_service.summarize_and_update(
        conversation_id=req.conversation_id,
        message_ids=message_ids,
        comment=req.comment,
        persona_key=persona_key,
    )
    logger.info(
        "api_feedback_done persona=%s conversation=%s accepted=%s pref_version=%s summary=%s",
        persona_key,
        req.conversation_id,
        result["accepted_count"],
        result["preference_version"],
        result["summary"],
    )
    return FeedbackResponse(
        ok=True,
        accepted_count=int(result["accepted_count"]),
        preference_version=int(result["preference_version"]),
        summary=str(result["summary"]),
    )
