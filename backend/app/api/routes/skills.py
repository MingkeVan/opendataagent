from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.api import SkillDetailResponse, SkillSummaryResponse
from app.services.skill_loader import get_skill_loader

router = APIRouter()


@router.get("", response_model=list[SkillSummaryResponse])
def list_skills() -> list[dict]:
    loader = get_skill_loader()
    return [
        {
            "id": skill.id,
            "name": skill.name,
            "version": skill.version,
            "description": skill.description,
            "engine": skill.engine,
            "renderers": skill.manifest.get("renderers", {}),
        }
        for skill in loader.list()
    ]


@router.get("/{skill_id}", response_model=SkillDetailResponse)
def get_skill(skill_id: str) -> dict:
    loader = get_skill_loader()
    try:
        skill = loader.get(skill_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Skill not found") from exc
    return {
        "id": skill.id,
        "name": skill.name,
        "version": skill.version,
        "description": skill.description,
        "engine": skill.engine,
        "renderers": skill.manifest.get("renderers", {}),
        "manifest": skill.manifest,
        "prompt_text": skill.prompt_text,
    }


@router.post("/reload")
def reload_skills(session: Session = Depends(get_db)) -> dict:
    loader = get_skill_loader()
    loader.reload()
    loader.ensure_snapshots(session)
    return {"status": "ok", "count": len(loader.list())}

