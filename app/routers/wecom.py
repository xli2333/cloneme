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


def _handle_text_message(msg: dict[str, str]) -> None:
    from_user = msg.get("FromUserName", "").strip()
    content = msg.get("Content", "").strip()
    agent_id = msg.get("AgentID", "").strip() or str(settings.wecom_agent_id)
    if not from_user or not content:
        return

    conversation_id = f"wecom:{agent_id}:{from_user.lower()}"
    user_message_id = memory_service.add_message(
        conversation_id=conversation_id,
        role="user",
        content=content,
        message_type="text",
        metadata={"source": "wecom"},
    )

    reply_text = ""
    try:
        result = generation_service.generate(conversation_id, content)
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
                    "bubble_index": idx,
                    "delay_ms": int(delays[idx] if idx < len(delays) else 0),
                },
            )
            assistant_ids.append(aid)
        memory_service.save_candidates(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            candidates=result.candidates,
            selected_index=result.selected_index,
        )
        reply_text = "\n".join([x.strip() for x in result.bubbles if x.strip()]).strip()
    except Exception as exc:
        logger.exception("wecom generation failed: %s", exc)
        fallback = "我收到了，稍等我再发你。"
        reply_text = fallback
        memory_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=fallback,
            message_type="text",
            metadata={"source": "wecom", "fallback": True},
        )

    if not reply_text:
        reply_text = "我在。"
    try:
        wecom_client.send_text_message(from_user, reply_text)
    except WeComApiError as exc:
        logger.error("wecom send failed: user=%s error=%s", from_user, exc)


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
