from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.api import ConversationCreateRequest, ConversationResponse, MessageCreateRequest, MessageCreateResponse, MessageResponse
from app.services.conversation_service import (
    create_conversation,
    get_conversation,
    list_conversations,
    list_messages,
    serialize_conversation,
    serialize_message,
)
from app.services.run_service import create_run

router = APIRouter()


@router.post("", response_model=ConversationResponse)
def create_conversation_route(payload: ConversationCreateRequest, session: Session = Depends(get_db)) -> dict:
    conversation = create_conversation(session, payload.title, payload.skillId)
    return serialize_conversation(conversation)


@router.get("", response_model=list[ConversationResponse])
def list_conversations_route(session: Session = Depends(get_db)) -> list[dict]:
    return [serialize_conversation(item) for item in list_conversations(session)]


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation_route(conversation_id: str, session: Session = Depends(get_db)) -> dict:
    conversation = get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return serialize_conversation(conversation)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
def list_messages_route(conversation_id: str, session: Session = Depends(get_db)) -> list[dict]:
    conversation = get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [serialize_message(item) for item in list_messages(session, conversation_id)]


@router.post("/{conversation_id}/messages", response_model=MessageCreateResponse)
def create_message_route(conversation_id: str, payload: MessageCreateRequest, session: Session = Depends(get_db)) -> dict:
    conversation = get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user_message, assistant_message, run = create_run(session, conversation, payload.content)
    return {
        "conversationId": conversation.id,
        "userMessageId": user_message.id,
        "assistantMessageId": assistant_message.id,
        "runId": run.id,
        "status": run.status,
    }

