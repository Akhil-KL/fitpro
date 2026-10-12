from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=2000)


class UpdatedEntity(BaseModel):
    type: str  # food_log | custom_food | workout_session | weight_log | water_log
    id: uuid.UUID
    action: Literal["created", "updated", "deleted"]


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    message: str
    intent: str
    status: Literal["completed", "needs_clarification", "failed", "answered"]
    result: dict[str, Any] | None = None
    updated_entities: list[UpdatedEntity] = []
    clarification: dict[str, Any] | None = None
    parser: str | None = None


class ConversationOut(ORMModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(ORMModel):
    id: uuid.UUID
    role: str
    content: str
    parsed_intent: str | None
    parsed_payload: dict[str, Any] | None = None  # assistant: {"status", "result"} so the UI can redraw receipts
    created_at: datetime
