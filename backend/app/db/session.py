from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine = None
_server_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.mysql_url,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_server_engine():
    global _server_engine
    if _server_engine is None:
        settings = get_settings()
        _server_engine = create_engine(
            settings.mysql_server_url,
            pool_pre_ping=True,
            future=True,
        )
    return _server_engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _session_factory


def get_db():
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope():
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_db_state() -> None:
    global _engine, _server_engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    if _server_engine is not None:
        _server_engine.dispose()
    _engine = None
    _server_engine = None
    _session_factory = None
