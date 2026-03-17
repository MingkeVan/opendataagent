from __future__ import annotations

from sqlalchemy import select

from app.db.session import session_scope
from app.models.entities import Conversation, Run
from app.worker.main import process_next_run


def test_worker_marks_run_failed_without_exiting(monkeypatch, client) -> None:
    conversation = client.post("/api/conversations", json={"title": "worker failure", "skillId": "demo-analyst"}).json()
    payload = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "这个请求会触发 worker 异常", "attachments": []},
    ).json()

    monkeypatch.setattr("app.engines.claude_agent_sdk.ClaudeAgentSdkAdapter.launch", lambda self, **_: object())
    monkeypatch.setattr(
        "app.engines.claude_agent_sdk.ClaudeAgentSdkAdapter.iter_raw_events",
        lambda self, process: (_ for _ in ()).throw(RuntimeError("simulated runtime failure")),
    )

    processed = process_next_run()
    assert processed == payload["runId"]

    with session_scope() as session:
        run = session.scalar(select(Run).where(Run.id == payload["runId"]))
        conversation_row = session.scalar(select(Conversation).where(Conversation.id == conversation["id"]))

        assert run is not None
        assert run.status == "failed"
        assert run.error_code == "worker_error"
        assert "simulated runtime failure" in str(run.error_message)

        assert conversation_row is not None
        assert conversation_row.status == "failed"
        assert conversation_row.active_run_id is None
