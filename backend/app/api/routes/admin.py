from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.skill_loader import get_skill_loader

router = APIRouter()


@router.post("/skills/reload")
def reload_skills_admin(session: Session = Depends(get_db)) -> dict:
    loader = get_skill_loader()
    loader.reload()
    loader.ensure_snapshots(session)
    return {"status": "ok", "count": len(loader.list())}
