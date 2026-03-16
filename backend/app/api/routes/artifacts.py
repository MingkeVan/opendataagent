from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.api import ArtifactResponse
from app.services.artifact_service import get_artifact, serialize_artifact

router = APIRouter()


@router.get("/{artifact_id}", response_model=ArtifactResponse)
def get_artifact_route(artifact_id: str, session: Session = Depends(get_db)) -> dict:
    artifact = get_artifact(session, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return serialize_artifact(artifact)
