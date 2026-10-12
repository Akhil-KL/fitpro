from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, Timestamps, UUIDPk, utcnow


class WeightLog(UUIDPk, Base):
    __tablename__ = "weight_logs"
    __table_args__ = (
        Index("ix_weight_logs_user_id_logged_at", "user_id", "logged_at"),
        CheckConstraint("weight_kg > 0", name="weight_positive"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class WaterLog(UUIDPk, Base):
    __tablename__ = "water_logs"
    __table_args__ = (
        Index("ix_water_logs_user_id_logged_at", "user_id", "logged_at"),
        CheckConstraint("amount_ml > 0", name="amount_positive"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Conversation(UUIDPk, Timestamps, Base):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(160))
    # Structured conversation state: pending clarifications, last referenced entities.
    state: Mapped[dict | None] = mapped_column(JSONType)

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class ChatMessage(UUIDPk, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_conversation_id_created_at", "conversation_id", "created_at"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_intent: Mapped[str | None] = mapped_column(String(40))
    parsed_payload: Mapped[dict | None] = mapped_column(JSONType)  # audit/debug only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Document(UUIDPk, Base):
    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf | txt
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)  # never returned to clients
    processing_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["WeightLog", "WaterLog", "Conversation", "ChatMessage", "Document"]
