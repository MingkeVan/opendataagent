from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str
    api_prefix: str
    environment: str
    debug: bool
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    stream_poll_interval_ms: int
    worker_poll_interval_ms: int
    artifact_inline_threshold_bytes: int
    frontend_origin: str
    agent_mode: str
    claude_agent_use_fixture_data: bool
    claude_agent_fixture_delay_ms: int
    python_executable: str
    claude_cli_path: str | None
    claude_sdk_timeout_seconds: int
    anthropic_api_key: str | None
    anthropic_base_url: str | None
    anthropic_model: str
    agent_data_mysql_host: str
    agent_data_mysql_port: int
    agent_data_mysql_user: str
    agent_data_mysql_password: str
    agent_data_mysql_database: str
    agent_sql_max_rows: int
    skills_dir: Path
    repo_root: Path
    backend_root: Path

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_origin]

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def mysql_server_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/?charset=utf8mb4"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    if sys.version_info < (3, 10):
        raise RuntimeError("OpenDataAgent backend now requires Python 3.10+")
    repo_root = Path(__file__).resolve().parents[3]
    backend_root = repo_root / "backend"
    skills_dir = Path(os.getenv("SKILLS_DIR", repo_root / "skills"))
    return Settings(
        app_name=os.getenv("APP_NAME", "OpenDataAgent"),
        api_prefix="/api",
        environment=os.getenv("APP_ENV", "development"),
        debug=os.getenv("APP_DEBUG", "false").lower() == "true",
        mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
        mysql_user=os.getenv("MYSQL_USER", "root"),
        mysql_password=os.getenv("MYSQL_PASSWORD", "root"),
        mysql_database=os.getenv("MYSQL_DATABASE", "opendata_agent"),
        stream_poll_interval_ms=int(os.getenv("STREAM_POLL_INTERVAL_MS", "250")),
        worker_poll_interval_ms=int(os.getenv("WORKER_POLL_INTERVAL_MS", "500")),
        artifact_inline_threshold_bytes=int(
            os.getenv("ARTIFACT_INLINE_THRESHOLD_BYTES", str(256 * 1024))
        ),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173"),
        agent_mode=os.getenv("CLAUDE_AGENT_MODE", "claude-agent-sdk"),
        claude_agent_use_fixture_data=os.getenv("CLAUDE_AGENT_USE_FIXTURE_DATA", "false").lower() == "true",
        claude_agent_fixture_delay_ms=int(os.getenv("CLAUDE_AGENT_FIXTURE_DELAY_MS", "0")),
        python_executable=os.getenv("PYTHON_EXECUTABLE", sys.executable),
        claude_cli_path=os.getenv("CLAUDE_CLI_PATH") or None,
        claude_sdk_timeout_seconds=int(os.getenv("CLAUDE_SDK_TIMEOUT_SECONDS", "180")),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6"),
        agent_data_mysql_host=os.getenv("AGENT_DATA_MYSQL_HOST", os.getenv("MYSQL_HOST", "127.0.0.1")),
        agent_data_mysql_port=int(os.getenv("AGENT_DATA_MYSQL_PORT", os.getenv("MYSQL_PORT", "3306"))),
        agent_data_mysql_user=os.getenv("AGENT_DATA_MYSQL_USER", os.getenv("MYSQL_USER", "root")),
        agent_data_mysql_password=os.getenv("AGENT_DATA_MYSQL_PASSWORD", os.getenv("MYSQL_PASSWORD", "root")),
        agent_data_mysql_database=os.getenv("AGENT_DATA_MYSQL_DATABASE", "demo_analytics"),
        agent_sql_max_rows=int(os.getenv("AGENT_SQL_MAX_ROWS", "200")),
        skills_dir=skills_dir,
        repo_root=repo_root,
        backend_root=backend_root,
    )


def reset_settings_cache() -> None:
    get_settings.cache_clear()
