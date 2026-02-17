from __future__ import annotations

import logging
import threading
import time
import xml.etree.ElementTree as ET

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from ..config import settings
from ..services.generation import generation_service
from ..services.memory import memory_service
from ..services.persona_routing import resolve_persona_key_from_user_id
from ..services.wecom_client import WeComApiError, wecom_client
from ..services.wecom_crypto import WeComCrypto, WeComCryptoError

router = APIRouter(tags=["wecom"])
logger = logging.getLogger("doppelganger.wecom")
CALLBACK_PATH = settings.wecom_callback_path if settings.wecom_callback_path.startswith("/") else "/wecom/callback"

_seen_messages: dict[str, float] = {}
_seen_lock = threading.Lock()


def _validate_crypto_settings() -> None:
    missing: list[str] = []
    if not settings.wecom_corp_id:
        missing.append("WECOM_CORP_ID")
    if not settings.wecom_token:
        missing.append("WECOM_TOKEN")
    if not settings.wecom_encoding_aes_key:
        missing.append("WECOM_ENCODING_AES_KEY")
    if missing:
        raise HTTPException(status_code=500, detail=f"missing settings: {', '.join(missing)}")


def _crypto() -> WeComCrypto:
    return WeComCrypto(
        token=settings.wecom_token,
        encoding_aes_key=settings.wecom_encoding_aes_key,
        receive_id=settings.wecom_corp_id,
    )


def _parse_plain_xml(xml_text: str) -> dict[str, str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise WeComCryptoError("invalid decrypted xml") from exc
    return {child.tag: (child.text or "").strip() for child in root}


def _build_dedupe_key(msg: dict[str, str]) -> str:
    msg_id = msg.get("MsgId", "").strip()
    if msg_id:
        return f"msgid:{msg_id}"
    return ":".join(
        [
            "evt",
            msg.get("FromUserName", ""),
            msg.get("CreateTime", ""),
            msg.get("MsgType", ""),
            msg.get("Event", ""),
        ]
    )


def _seen_before(key: str, ttl_seconds: int = 600) -> bool:
    now = time.time()
    with _seen_lock:
        for k, ts in list(_seen_messages.items()):
            if now - ts > ttl_seconds:
                _seen_messages.pop(k, None)
        if key in _seen_messages:
            return True
        _seen_messages[key] = now
    return False


def _fallback_text(content: str, persona_key: str) -> str:
    snippet = content.strip().replace("\n", " ")
    if len(snippet) > 24:
        snippet = snippet[:24] + "…"
    if persona_key == settings.dxa_persona_key:
        return f"{settings.strict_nickname}，我在，先按你这句「{snippet}」接着聊。"
    return f"我在，先按你这句「{snippet}」接着聊。"


def _log_rag_overview(persona_key: str, conversation_id: str, debug: dict) -> None:
    rag = dict(debug.get("rag_overview", {}) or {})
    logger.info(
        "wecom_generate_done mode=%s conversation=%s final_path=%s rag_blocks=%s top_segment_ids=%s",
        persona_key,
        conversation_id,
        str(debug.get("final_path", "")),
        dict(rag.get("blocks", {}) or {}),
        [int(x.get("segment_id", 0)) for x in list(rag.get("top_segments", []) or [])[:5]],
    )


def _handle_text_message(msg: dict[str, str]) -> None:
    from_user = msg.get("FromUserName", "").strip()
    content = msg.get("Content", "").strip()
    agent_id = msg.get("AgentID", "").strip() or str(settings.wecom_agent_id)
    if not from_user or not content:
        return

    persona_key = resolve_persona_key_from_user_id(from_user)
    conversation_id = f"wecom:{agent_id}:{from_user.lower()}"
    logger.info(
        "wecom_in mode=%s conversation=%s from_user=%s text=%s",
        persona_key,
        conversation_id,
        from_user,
        content,
    )
    user_message_id = memory_service.add_message(
        conversation_id=conversation_id,
        role="user",
        content=content,
        message_type="text",
        metadata={"source": "wecom", "persona_key": persona_key},
    )
    user_meta = memory_service.get_message_meta(user_message_id)
    memory_service.upsert_time_state(
        conversation_id=conversation_id,
        persona_key=persona_key,
        last_user_at=str((user_meta or {}).get("created_at") or ""),
    )

    reply_text = ""
    try:
        result = generation_service.generate(
            conversation_id,
            content,
            persona_key=persona_key,
        )
        delays = result.debug.get("delays", [])
        assistant_ids: list[int] = []
        for idx, bubble in enumerate(result.bubbles):
            aid = memory_service.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=bubble,
                message_type="text",
                metadata={
                    "source": "wecom",
                    "persona_key": persona_key,
                    "bubble_index": idx,
                    "delay_ms": int(delays[idx] if idx < len(delays) else 0),
                },
            )
            memory_service.maybe_add_followup(
                conversation_id=conversation_id,
                persona_key=persona_key,
                source_message_id=aid,
                owner_role="assistant",
                content=bubble,
            )
            assistant_ids.append(aid)
        memory_service.save_candidates(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            candidates=result.candidates,
            selected_index=result.selected_index,
        )
        if assistant_ids:
            last_meta = memory_service.get_message_meta(assistant_ids[-1])
            memory_service.upsert_time_state(
                conversation_id=conversation_id,
                persona_key=persona_key,
                last_assistant_at=str((last_meta or {}).get("created_at") or ""),
                last_time_ack_at=(
                    str((last_meta or {}).get("created_at") or "")
                    if bool(result.debug.get("time_ack_used"))
                    else None
                ),
            )
        _log_rag_overview(persona_key, conversation_id, result.debug)
        reply_text = "\n".join([x.strip() for x in result.bubbles if x.strip()]).strip()
    except Exception as exc:
        logger.exception("wecom generation failed mode=%s conversation=%s error=%s", persona_key, conversation_id, exc)
        reply_text = _fallback_text(content, persona_key)
        aid = memory_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply_text,
            message_type="text",
            metadata={"source": "wecom", "persona_key": persona_key, "fallback": True},
        )
        assistant_meta = memory_service.get_message_meta(aid)
        memory_service.upsert_time_state(
            conversation_id=conversation_id,
            persona_key=persona_key,
            last_assistant_at=str((assistant_meta or {}).get("created_at") or ""),
        )

    if not reply_text:
        reply_text = _fallback_text(content, persona_key)
    try:
        wecom_client.send_text_message(from_user, reply_text)
    except WeComApiError as exc:
        logger.error("wecom send failed: user=%s mode=%s error=%s", from_user, persona_key, exc)


@router.get(CALLBACK_PATH)
def verify_callback(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
) -> PlainTextResponse:
    _validate_crypto_settings()
    try:
        plain = _crypto().verify_url(msg_signature, timestamp, nonce, echostr)
    except WeComCryptoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlainTextResponse(plain, status_code=200)


@router.post(CALLBACK_PATH)
async def receive_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
) -> PlainTextResponse:
    _validate_crypto_settings()
    body = (await request.body()).decode("utf-8", errors="ignore")

    try:
        plain_xml = _crypto().decrypt_message(body, msg_signature, timestamp, nonce)
        msg = _parse_plain_xml(plain_xml)
    except WeComCryptoError as exc:
        logger.warning("wecom callback decrypt failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("wecom callback parse failed: %s", exc)
        raise HTTPException(status_code=400, detail="invalid callback body") from exc

    dedupe_key = _build_dedupe_key(msg)
    if _seen_before(dedupe_key):
        return PlainTextResponse("", status_code=200)

    msg_type = msg.get("MsgType", "").lower()
    if msg_type == "text":
        background_tasks.add_task(_handle_text_message, msg)
    else:
        logger.info("wecom skip msg_type=%s", msg_type or "unknown")

    return PlainTextResponse("", status_code=200)

