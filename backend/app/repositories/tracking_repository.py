from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ChatMessage, Conversation, Document, WaterLog, WeightLog


class TrackingRepository:
    """Weight and water logs (user-scoped)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _page(self, model, user_id: uuid.UUID, limit: int, offset: int, start: datetime | None, end: datetime | None):
        conds = [model.user_id == user_id]
        if start is not None:
            conds.append(model.logged_at >= start)
        if end is not None:
            conds.append(model.logged_at < end)
        total = self.db.scalar(select(func.count()).select_from(model).where(*conds)) or 0
        rows = self.db.scalars(select(model).where(*conds).order_by(model.logged_at.desc()).offset(offset).limit(limit))
        return list(rows), total

    def weight_page(self, user_id, limit, offset, start=None, end=None):
        return self._page(WeightLog, user_id, limit, offset, start, end)

    def water_page(self, user_id, limit, offset, start=None, end=None):
        return self._page(WaterLog, user_id, limit, offset, start, end)

    def weights_between(self, user_id: uuid.UUID, start: datetime | None, end: datetime) -> list[WeightLog]:
        conds = [WeightLog.user_id == user_id, WeightLog.logged_at < end]
        if start is not None:
            conds.append(WeightLog.logged_at >= start)
        return list(self.db.scalars(select(WeightLog).where(*conds).order_by(WeightLog.logged_at)))

    def first_weight(self, user_id: uuid.UUID) -> WeightLog | None:
        return self.db.scalar(select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.logged_at).limit(1))

    def latest_weight(self, user_id: uuid.UUID, before: datetime | None = None) -> WeightLog | None:
        stmt = select(WeightLog).where(WeightLog.user_id == user_id)
        if before is not None:
            stmt = stmt.where(WeightLog.logged_at < before)
        return self.db.scalar(stmt.order_by(WeightLog.logged_at.desc()).limit(1))

    def water_between(self, user_id: uuid.UUID, start: datetime, end: datetime) -> list[WaterLog]:
        return list(
            self.db.scalars(
                select(WaterLog).where(WaterLog.user_id == user_id, WaterLog.logged_at >= start, WaterLog.logged_at < end)
            )
        )


class ChatRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def conversation(self, user_id: uuid.UUID, conv_id: uuid.UUID) -> Conversation | None:
        return self.db.scalar(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id))

    def latest_conversation(self, user_id: uuid.UUID) -> Conversation | None:
        return self.db.scalar(
            select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc()).limit(1)
        )

    def conversations_page(self, user_id: uuid.UUID, limit: int, offset: int):
        total = self.db.scalar(select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)) or 0
        rows = self.db.scalars(
            select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc())
            .offset(offset).limit(limit)
        )
        return list(rows), total

    def recent_messages(self, conv_id: uuid.UUID, limit: int) -> list[ChatMessage]:
        rows = self.db.scalars(
            select(ChatMessage).where(ChatMessage.conversation_id == conv_id)
            .order_by(ChatMessage.created_at.desc()).limit(limit)
        )
        return list(reversed(list(rows)))

    def messages_page(self, conv_id: uuid.UUID, limit: int, offset: int):
        """Newest first so page 1 is the latest messages; the client reverses for display."""
        total = self.db.scalar(select(func.count()).select_from(ChatMessage).where(ChatMessage.conversation_id == conv_id)) or 0
        rows = self.db.scalars(
            select(ChatMessage).where(ChatMessage.conversation_id == conv_id)
            .order_by(ChatMessage.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows), total


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: uuid.UUID, doc_id: uuid.UUID) -> Document | None:
        return self.db.scalar(select(Document).where(Document.id == doc_id, Document.user_id == user_id))

    def list(self, user_id: uuid.UUID, limit: int = 50) -> list[Document]:
        return list(
            self.db.scalars(select(Document).where(Document.user_id == user_id).order_by(Document.created_at.desc()).limit(limit))
        )
