import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, DbSession, chat_rate_limit
from app.core.errors import NotFound
from app.repositories.tracking_repository import ChatRepository
from app.schemas.chat import ChatMessageOut, ChatRequest, ChatResponse, ConversationOut
from app.schemas.common import Page
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages", response_model=ChatResponse, dependencies=[Depends(chat_rate_limit)])
def send_message(body: ChatRequest, user: CurrentUser, db: DbSession) -> ChatResponse:
    return ChatService(db).handle(user, body)


@router.get("/conversations", response_model=Page[ConversationOut])
def list_conversations(
    user: CurrentUser, db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ConversationOut]:
    rows, total = ChatRepository(db).conversations_page(user.id, page_size, (page - 1) * page_size)
    return Page(items=[ConversationOut.model_validate(r) for r in rows], page=page, page_size=page_size, total=total)


@router.get("/conversations/{conversation_id}/messages", response_model=Page[ChatMessageOut])
def list_messages(
    conversation_id: uuid.UUID, user: CurrentUser, db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[ChatMessageOut]:
    repo = ChatRepository(db)
    if repo.conversation(user.id, conversation_id) is None:
        raise NotFound("Conversation not found.")
    rows, total = repo.messages_page(conversation_id, page_size, (page - 1) * page_size)
    return Page(items=[ChatMessageOut.model_validate(r) for r in rows], page=page, page_size=page_size, total=total)
