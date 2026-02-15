from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=3000)


class Bubble(BaseModel):
    text: str
    delay_ms: int = 0


class ChatResponse(BaseModel):
    conversation_id: str
    user_message_id: int
    assistant_message_ids: list[int]
    bubbles: list[Bubble]
    debug: dict[str, Any] = Field(default_factory=dict)


class MessageDTO(BaseModel):
    id: int
    role: str
    content: str
    created_at: str
    message_type: str = "text"
    feedback_score: int = 0


class FeedbackRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    message_ids: list[int] = Field(min_length=1)
    comment: str = Field(default="", max_length=500)


class FeedbackResponse(BaseModel):
    ok: bool
    accepted_count: int
    preference_version: int
    summary: str


class ConversationResponse(BaseModel):
    conversation_id: str
    messages: list[MessageDTO]


class SearchResultDTO(BaseModel):
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultDTO]


class HealthResponse(BaseModel):
    status: str
    env: str
    model_pro: str
    model_flash: str

