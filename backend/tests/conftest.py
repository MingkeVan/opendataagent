from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MYSQL_HOST", "127.0.0.1")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "root")
os.environ.setdefault("MYSQL_PASSWORD", "root")
os.environ.setdefault("MYSQL_DATABASE", "opendata_agent_test")
os.environ.setdefault("CLAUDE_AGENT_MODE", "mock")
os.environ.setdefault("MOCK_AGENT_DELAY_MS", "0")

from app.core.config import reset_settings_cache
from app.db.init_schema import reset_schema
from app.db.session import reset_db_state
from app.main import app
from app.services.skill_loader import get_skill_loader, reset_skill_loader


@pytest.fixture(autouse=True)
def reset_environment() -> Iterator[None]:
    reset_settings_cache()
    reset_db_state()
    reset_skill_loader()
    reset_schema()
    loader = get_skill_loader()
    loader.reload()
    yield
    reset_db_state()


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client

