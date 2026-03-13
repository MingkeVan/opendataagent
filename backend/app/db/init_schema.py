from __future__ import annotations

from sqlalchemy import text

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine, get_server_engine
from app.models.entities import Artifact, Conversation, Message, Run, RunEvent, SkillSnapshot, ToolCall


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


def reset_schema() -> None:
    ensure_database()
    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine())

