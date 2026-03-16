from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import Artifact


def get_artifact(session: Session, artifact_id: str) -> Artifact | None:
    return session.get(Artifact, artifact_id)


def serialize_artifact(artifact: Artifact) -> dict:
    return {
        "id": artifact.id,
        "runId": artifact.run_id,
        "conversationId": artifact.conversation_id,
        "artifactType": artifact.artifact_type,
        "mimeType": artifact.mime_type,
        "sizeBytes": artifact.size_bytes,
        "contentJson": artifact.content_json,
        "contentText": artifact.content_text,
        "metadataJson": artifact.metadata_json or {},
        "createdAt": artifact.created_at.isoformat(),
    }
