from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.ids import new_id
from app.models.entities import SkillSnapshot


@dataclass
class LoadedSkill:
    id: str
    name: str
    description: str
    version: str
    engine: str
    manifest: dict
    prompt_text: str
    content_hash: str
    directory: Path


class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills: dict[str, LoadedSkill] = {}

    def reload(self) -> dict[str, LoadedSkill]:
        skills: dict[str, LoadedSkill] = {}
        if not self.skills_dir.exists():
            self._skills = {}
            return self._skills

        for manifest_path in sorted(self.skills_dir.glob("*/skill.yaml")):
            directory = manifest_path.parent
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            prompt_rel = manifest.get("entry_prompt", "./prompt.md")
            prompt_path = (directory / prompt_rel).resolve()
            prompt_text = prompt_path.read_text(encoding="utf-8")
            payload = manifest_path.read_text(encoding="utf-8") + "\n" + prompt_text
            content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            skill = LoadedSkill(
                id=manifest["id"],
                name=manifest["name"],
                description=manifest.get("description", ""),
                version=manifest["version"],
                engine=manifest["engine"],
                manifest=manifest,
                prompt_text=prompt_text,
                content_hash=content_hash,
                directory=directory,
            )
            skills[skill.id] = skill
        self._skills = skills
        return self._skills

    def list(self) -> list[LoadedSkill]:
        return list(self._skills.values())

    def get(self, skill_id: str) -> LoadedSkill:
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(skill_id)
        return skill

    def ensure_snapshots(self, session: Session) -> None:
        for skill in self._skills.values():
            existing = session.scalar(
                select(SkillSnapshot).where(
                    SkillSnapshot.skill_id == skill.id,
                    SkillSnapshot.skill_version == skill.version,
                    SkillSnapshot.content_hash == skill.content_hash,
                )
            )
            if existing is None:
                session.add(
                    SkillSnapshot(
                        id=new_id("skill"),
                        skill_id=skill.id,
                        skill_version=skill.version,
                        content_hash=skill.content_hash,
                        manifest_json=skill.manifest,
                        prompt_text=skill.prompt_text,
                    )
                )
        session.commit()

    def get_or_create_snapshot(self, session: Session, skill_id: str) -> SkillSnapshot:
        skill = self.get(skill_id)
        snapshot = session.scalar(
            select(SkillSnapshot).where(
                SkillSnapshot.skill_id == skill.id,
                SkillSnapshot.skill_version == skill.version,
                SkillSnapshot.content_hash == skill.content_hash,
            )
        )
        if snapshot is None:
            snapshot = SkillSnapshot(
                id=new_id("skill"),
                skill_id=skill.id,
                skill_version=skill.version,
                content_hash=skill.content_hash,
                manifest_json=skill.manifest,
                prompt_text=skill.prompt_text,
            )
            session.add(snapshot)
            session.commit()
        return snapshot


_skill_loader: SkillLoader | None = None


def get_skill_loader() -> SkillLoader:
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader(get_settings().skills_dir)
        _skill_loader.reload()
    return _skill_loader


def reset_skill_loader() -> None:
    global _skill_loader
    _skill_loader = None

