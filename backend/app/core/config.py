from __future__ import annotations

import os
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
    mock_agent_delay_ms: int
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
        agent_mode=os.getenv("CLAUDE_AGENT_MODE", "mock"),
        mock_agent_delay_ms=int(os.getenv("MOCK_AGENT_DELAY_MS", "60")),
        skills_dir=skills_dir,
        repo_root=repo_root,
        backend_root=backend_root,
    )


def reset_settings_cache() -> None:
    get_settings.cache_clear()

