from __future__ import annotations

from ..config import settings


def resolve_persona_key_from_user_id(user_id: str) -> str:
    uid = (user_id or "").strip().lower()
    if "dxa" in uid:
        return settings.dxa_persona_key
    return settings.friends_persona_key


def resolve_persona_key_from_conversation_id(conversation_id: str) -> str:
    cid = (conversation_id or "").strip()
    if not cid:
        return settings.dxa_persona_key
    if cid.startswith("wecom:"):
        user_id = cid.split(":")[-1]
        return resolve_persona_key_from_user_id(user_id)
    return settings.dxa_persona_key
