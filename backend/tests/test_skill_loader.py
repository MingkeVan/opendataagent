from __future__ import annotations

from app.db.session import session_scope
from app.models.entities import SkillSnapshot
from app.services.skill_loader import get_skill_loader


def test_skill_loader_loads_demo_skill() -> None:
    loader = get_skill_loader()
    skills = loader.list()
    assert len(skills) == 1
    assert skills[0].id == "demo-analyst"
    assert "数据分析" in skills[0].prompt_text


def test_skill_loader_creates_snapshot() -> None:
    loader = get_skill_loader()
    with session_scope() as session:
        loader.ensure_snapshots(session)
        snapshots = session.query(SkillSnapshot).all()
        assert len(snapshots) == 1
        assert snapshots[0].skill_id == "demo-analyst"

