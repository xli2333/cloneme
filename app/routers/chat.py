from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..schemas import (
    Bubble,
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    MessageDTO,
)
from ..config import settings
from ..services.generation import generation_service
from ..services.memory import memory_service

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger("doppelganger.chat")


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="message cannot be empty")

    logger.info("api_chat_in conversation=%s text=%s", req.conversation_id, text)
    user_message_id = memory_service.add_message(
        conversation_id=req.conversation_id,
        role="user",
        content=text,
        message_type="text",
    )
    user_meta = memory_service.get_message_meta(user_message_id)
    memory_service.upsert_time_state(
        conversation_id=req.conversation_id,
        persona_key=settings.dxa_persona_key,
        last_user_at=str((user_meta or {}).get("created_at") or ""),
    )

    try:
        result = generation_service.generate(
            req.conversation_id,
            text,
            persona_key=settings.dxa_persona_key,
        )
    except Exception as exc:
        logger.exception("generation_error conversation=%s error=%s", req.conversation_id, exc)
        snippet = text[:36].strip()
        fallback_bubbles = [
            f"{settings.strict_nickname}，我在，先接住你这个点。",
            f"你刚刚说的是「{snippet}」，你继续我按这个接。",
        ]
        assistant_message_ids: list[int] = []
        for idx, bubble in enumerate(fallback_bubbles):
            aid = memory_service.add_message(
                conversation_id=req.conversation_id,
                role="assistant",
                content=bubble,
                message_type="text",
                metadata={
                    "bubble_index": idx,
                    "delay_ms": 500 + idx * 900,
                    "fallback": True,
                    "fallback_reason": "generation_exception",
                },
            )
            assistant_message_ids.append(aid)
            assistant_meta = memory_service.get_message_meta(aid)
            memory_service.upsert_time_state(
                conversation_id=req.conversation_id,
                persona_key=settings.dxa_persona_key,
                last_assistant_at=str((assistant_meta or {}).get("created_at") or ""),
            )
        return ChatResponse(
            conversation_id=req.conversation_id,
            user_message_id=user_message_id,
            assistant_message_ids=assistant_message_ids,
            bubbles=[
                Bubble(text=fallback_bubbles[0], delay_ms=500),
                Bubble(text=fallback_bubbles[1], delay_ms=1400),
            ],
            debug={"fallback": True, "error": str(exc)},
        )

    assistant_message_ids: list[int] = []
    delays = result.debug.get("delays", [])
    for idx, bubble in enumerate(result.bubbles):
        aid = memory_service.add_message(
            conversation_id=req.conversation_id,
            role="assistant",
            content=bubble,
            message_type="text",
            metadata={"bubble_index": idx, "delay_ms": delays[idx] if idx < len(delays) else 0},
        )
        memory_service.maybe_add_followup(
            conversation_id=req.conversation_id,
            persona_key=settings.dxa_persona_key,
            source_message_id=aid,
            owner_role="assistant",
            content=bubble,
        )
        assistant_message_ids.append(aid)

    if assistant_message_ids:
        last_meta = memory_service.get_message_meta(assistant_message_ids[-1])
        memory_service.upsert_time_state(
            conversation_id=req.conversation_id,
            persona_key=settings.dxa_persona_key,
            last_assistant_at=str((last_meta or {}).get("created_at") or ""),
            last_time_ack_at=(
                str((last_meta or {}).get("created_at") or "")
                if bool(result.debug.get("time_ack_used"))
                else None
            ),
        )

    memory_service.save_candidates(
        conversation_id=req.conversation_id,
        user_message_id=user_message_id,
        candidates=result.candidates,
        selected_index=result.selected_index,
    )

    bubbles = [
        Bubble(text=text_item, delay_ms=int(delays[i] if i < len(delays) else 0))
        for i, text_item in enumerate(result.bubbles)
    ]

    return ChatResponse(
        conversation_id=req.conversation_id,
        user_message_id=user_message_id,
        assistant_message_ids=assistant_message_ids,
        bubbles=bubbles,
        debug={
            **result.debug,
            "planner_model": result.planner_model,
            "generator_model": result.generator_model,
            "critic_model": result.critic_model,
        },
    )


@router.get("/conversation/{conversation_id}", response_model=ConversationResponse)
def conversation(conversation_id: str) -> ConversationResponse:
    rows = memory_service.list_messages(conversation_id, limit=200)
    messages = [
        MessageDTO(
            id=int(r["id"]),
            role=str(r["role"]),
            content=str(r["content"]),
            created_at=str(r["created_at"]),
            message_type=str(r["message_type"]),
            feedback_score=int(r["feedback_score"]),
        )
        for r in rows
    ]
    return ConversationResponse(conversation_id=conversation_id, messages=messages)
