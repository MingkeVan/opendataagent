from __future__ import annotations

from sqlalchemy import select

from app.db.session import session_scope
from app.models.entities import Conversation, Run
from app.services.run_service import create_run, reconcile_inflight_runs
from app.services.skill_loader import get_skill_loader


def test_reconcile_inflight_runs_fails_running_and_cancels_queued() -> None:
    with session_scope() as session:
        snapshot = get_skill_loader().get_or_create_snapshot(session, "demo-analyst")

        running_conversation = Conversation(
            id="conv_running",
            title="running",
            skill_id=snapshot.skill_id,
            skill_version=snapshot.skill_version,
            status="running",
            active_run_id="run_running",
        )
        cancelled_conversation = Conversation(
            id="conv_cancelled",
            title="cancelled",
            skill_id=snapshot.skill_id,
            skill_version=snapshot.skill_version,
            status="running",
            active_run_id=None,
        )
        session.add_all([running_conversation, cancelled_conversation])
        session.flush()

        _, _, running_run = create_run(session, running_conversation, "运行中的问题")
        queued_user, queued_assistant, queued_run = create_run(session, cancelled_conversation, "取消前的问题")

        running_run.status = "running"
        running_conversation.active_run_id = running_run.id
        running_conversation.status = "running"

        queued_run.status = "queued"
        queued_run.cancel_requested = True
        queued_assistant.status = "queued"
        cancelled_conversation.active_run_id = queued_run.id
        cancelled_conversation.status = "running"

        session.flush()
        reconcile_inflight_runs(session)
        session.commit()

        running_run_id = running_run.id
        queued_run_id = queued_run.id
        running_conversation_id = running_conversation.id
        cancelled_conversation_id = cancelled_conversation.id

    with session_scope() as session:
        refreshed_running = session.scalar(select(Run).where(Run.id == running_run_id))
        refreshed_cancelled = session.scalar(select(Run).where(Run.id == queued_run_id))
        running_conv = session.scalar(select(Conversation).where(Conversation.id == running_conversation_id))
        cancelled_conv = session.scalar(select(Conversation).where(Conversation.id == cancelled_conversation_id))

        assert refreshed_running is not None
        assert refreshed_running.status == "failed"
        assert refreshed_running.error_code == "worker_restarted"

        assert refreshed_cancelled is not None
        assert refreshed_cancelled.status == "cancelled"
        assert refreshed_cancelled.error_code == "cancelled"

        assert running_conv is not None
        assert running_conv.active_run_id is None

        assert cancelled_conv is not None
        assert cancelled_conv.active_run_id is None
