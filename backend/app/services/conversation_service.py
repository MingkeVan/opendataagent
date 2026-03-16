from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.core.time import utcnow
from app.models.entities import Conversation, Message
from app.services.skill_loader import get_skill_loader


def serialize_conversation(conversation: Conversation) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "skillId": conversation.skill_id,
        "skillVersion": conversation.skill_version,
        "status": conversation.status,
        "activeRunId": conversation.active_run_id,
        "updatedAt": conversation.updated_at.isoformat(),
    }


def serialize_message(message: Message) -> dict:
    return {
        "id": message.id,
        "conversationId": message.conversation_id,
        "runId": message.run_id,
        "role": message.role,
        "uiParts": message.ui_parts,
        "contentBlocks": message.content_blocks or [],
        "traceSummary": message.trace_summary,
        "finalText": message.final_text,
        "status": message.status,
        "createdAt": message.created_at.isoformat(),
    }


def create_conversation(session: Session, title: str | None, skill_id: str) -> Conversation:
    loader = get_skill_loader()
    snapshot = loader.get_or_create_snapshot(session, skill_id)
    conversation = Conversation(
        id=new_id("conv"),
        title=title or "新建会话",
        skill_id=snapshot.skill_id,
        skill_version=snapshot.skill_version,
        status="idle",
        last_message_at=utcnow(),
    )
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def list_conversations(session: Session) -> list[Conversation]:
    return list(
        session.scalars(select(Conversation).order_by(Conversation.updated_at.desc(), Conversation.created_at.desc()))
    )


def get_conversation(session: Session, conversation_id: str) -> Conversation | None:
    return session.get(Conversation, conversation_id)


def list_messages(session: Session, conversation_id: str) -> list[Message]:
    return list(
        session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
    )
