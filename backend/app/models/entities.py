from __future__ import annotations

from sqlalchemy import BIGINT, JSON, Boolean, Column, DateTime, Index, Integer, String, Text, UniqueConstraint

from app.core.time import utcnow
from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), nullable=True)
    title = Column(String(255), nullable=False)
    skill_id = Column(String(128), nullable=False)
    skill_version = Column(String(32), nullable=False)
    status = Column(String(32), default="idle", nullable=False)
    active_run_id = Column(String(36), nullable=True)
    summary = Column(Text, nullable=True)
    last_message_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        Index("idx_conv_last_message_at", "last_message_at"),
        Index("idx_conv_skill", "skill_id", "skill_version"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36), nullable=False, index=True)
    run_id = Column(String(36), nullable=True, index=True)
    role = Column(String(16), nullable=False)
    raw_blocks = Column(JSON, nullable=True)
    ui_parts = Column(JSON, nullable=False)
    content_blocks = Column(JSON, nullable=True)
    trace_summary = Column(JSON, nullable=True)
    final_text = Column(Text, nullable=True)
    usage_json = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=False), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=utcnow, onupdate=utcnow, nullable=False)


class MessageBlock(Base):
    __tablename__ = "message_blocks"

    id = Column(String(36), primary_key=True)
    message_id = Column(String(36), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=False, index=True)
    run_id = Column(String(36), nullable=True, index=True)
    role = Column(String(16), nullable=False)
    step_index = Column(Integer, nullable=True)
    block_index = Column(Integer, nullable=False)
    block_type = Column(String(64), nullable=False)
    tool_call_id = Column(String(128), nullable=True)
    visibility = Column(String(32), nullable=False, default="user")
    payload_json = Column(JSON, nullable=False)
    raw_provider_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=False), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("message_id", "block_index", name="uk_message_block_index"),
        Index("idx_message_block_message", "message_id", "block_index"),
        Index("idx_message_block_run", "run_id", "step_index", "block_index"),
    )


class Run(Base):
    __tablename__ = "runs"

    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36), nullable=False, index=True)
    skill_snapshot_id = Column(String(36), nullable=False)
    engine = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    cancel_requested = Column(Boolean, default=False, nullable=False)
    attempt_no = Column(Integer, default=1, nullable=False)
    stop_reason = Column(String(64), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    context_json = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=False), nullable=True)
    ended_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=utcnow, onupdate=utcnow, nullable=False)


class RunStep(Base):
    __tablename__ = "run_steps"

    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), nullable=False, index=True)
    step_index = Column(Integer, nullable=False)
    step_id = Column(String(128), nullable=False)
    title = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="running")
    agent_session_id = Column(String(128), nullable=True)
    model = Column(String(128), nullable=True)
    stop_reason = Column(String(64), nullable=True)
    usage_json = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=False), nullable=True)
    ended_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uk_run_step_index"),
        UniqueConstraint("run_id", "step_id", name="uk_run_step_id"),
        Index("idx_run_step_order", "run_id", "step_index"),
    )


class RunEvent(Base):
    __tablename__ = "run_events"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    run_id = Column(String(36), nullable=False, index=True)
    seq = Column(BIGINT, nullable=False)
    event_type = Column(String(64), nullable=False)
    payload_json = Column(JSON, nullable=False)
    raw_payload_json = Column(JSON, nullable=True)
    visible_in_history = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=False), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uk_run_seq"),
        Index("idx_run_event_tail", "run_id", "seq"),
        Index("idx_run_event_history", "run_id", "visible_in_history", "seq"),
    )


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), nullable=False, index=True)
    message_id = Column(String(36), nullable=True)
    step_index = Column(Integer, nullable=True)
    tool_call_id = Column(String(128), nullable=False)
    tool_name = Column(String(128), nullable=False)
    input_json = Column(JSON, nullable=True)
    output_summary = Column(JSON, nullable=True)
    artifact_id = Column(String(36), nullable=True)
    status = Column(String(32), nullable=False)
    latency_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=False), nullable=True)
    ended_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("run_id", "tool_call_id", name="uk_tool_call"),
        Index("idx_tool_run", "run_id", "created_at"),
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=False, index=True)
    artifact_type = Column(String(32), nullable=False)
    mime_type = Column(String(128), nullable=False)
    size_bytes = Column(BIGINT, nullable=False)
    content_json = Column(JSON, nullable=True)
    content_text = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=False), default=utcnow, nullable=False)


class SkillSnapshot(Base):
    __tablename__ = "skill_snapshots"

    id = Column(String(36), primary_key=True)
    skill_id = Column(String(128), nullable=False)
    skill_version = Column(String(32), nullable=False)
    content_hash = Column(String(128), nullable=False)
    manifest_json = Column(JSON, nullable=False)
    prompt_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=False), default=utcnow, nullable=False)

    __table_args__ = (Index("idx_skill_lookup", "skill_id", "skill_version", "created_at"),)
