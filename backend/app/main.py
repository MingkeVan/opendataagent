from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.db.init_schema import init_schema
from app.db.session import session_scope
from app.services.skill_loader import get_skill_loader

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
def startup_event() -> None:
    init_schema()
    loader = get_skill_loader()
    loader.reload()
    with session_scope() as session:
        loader.ensure_snapshots(session)

