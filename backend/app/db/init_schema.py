from __future__ import annotations

from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine, get_server_engine
from app.models.entities import (
    Artifact,
    Conversation,
    Message,
    MessageBlock,
    Run,
    RunEvent,
    RunStep,
    SkillSnapshot,
    ToolCall,
)


def ensure_database() -> None:
    settings = get_settings()
    with get_server_engine().begin() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` "
                "DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_0900_ai_ci"
            )
        )


def init_schema() -> None:
    ensure_database()
    Base.metadata.create_all(bind=get_engine())
    ensure_additive_schema()


def reset_schema() -> None:
    ensure_database()
    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine())


def ensure_additive_schema() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    inspector = inspect(engine)
    table_columns = {table_name: {column["name"] for column in inspector.get_columns(table_name)} for table_name in inspector.get_table_names()}
    statements: list[str] = []

    if "messages" in table_columns:
        missing = table_columns["messages"]
        if "content_blocks" not in missing:
            statements.append("ALTER TABLE messages ADD COLUMN content_blocks JSON NULL")
        if "trace_summary" not in missing:
            statements.append("ALTER TABLE messages ADD COLUMN trace_summary JSON NULL")
        if "final_text" not in missing:
            statements.append("ALTER TABLE messages ADD COLUMN final_text TEXT NULL")
        if "sequence_no" not in missing:
            statements.append("ALTER TABLE messages ADD COLUMN sequence_no INT NULL")

    if "runs" in table_columns and "context_json" not in table_columns["runs"]:
        statements.append("ALTER TABLE runs ADD COLUMN context_json JSON NULL")

    if "tool_calls" in table_columns and "step_index" not in table_columns["tool_calls"]:
        statements.append("ALTER TABLE tool_calls ADD COLUMN step_index INT NULL")

    if statements:
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))

    table_columns = {table_name: {column["name"] for column in inspector.get_columns(table_name)} for table_name in inspector.get_table_names()}
    if "messages" in table_columns and "sequence_no" in table_columns["messages"]:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE messages AS target
                    JOIN (
                        SELECT
                            id,
                            ROW_NUMBER() OVER (
                                PARTITION BY conversation_id
                                ORDER BY created_at ASC, id ASC
                            ) AS derived_sequence_no
                        FROM messages
                    ) AS ordered
                    ON ordered.id = target.id
                    SET target.sequence_no = ordered.derived_sequence_no
                    WHERE target.sequence_no IS NULL
                    """
                )
            )
