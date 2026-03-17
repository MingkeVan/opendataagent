from __future__ import annotations

import time

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import reset_settings_cache
from app.db.init_schema import reset_schema
from app.db.session import reset_db_state, session_scope
from app.main import app
from app.models.entities import Run
from app.services.skill_loader import get_skill_loader, reset_skill_loader
from app.worker.main import process_next_run


def test_conversation_run_and_history_flow(client) -> None:
    skills = client.get("/api/skills")
    assert skills.status_code == 200
    assert skills.json()[0]["id"] == "demo-analyst"

    create_conversation = client.post("/api/conversations", json={"title": "图表测试", "skillId": "demo-analyst"})
    assert create_conversation.status_code == 200
    conversation = create_conversation.json()

    create_message = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "请给我一个图表和表格来说明最近七天趋势", "attachments": []},
    )
    assert create_message.status_code == 200
    payload = create_message.json()
    run_id = payload["runId"]

    processed = process_next_run()
    assert processed == run_id

    assistant = None
    for _ in range(10):
        messages = client.get(f"/api/conversations/{conversation['id']}/messages")
        assert messages.status_code == 200
        body = messages.json()
        assert len(body) == 2
        assert [item["role"] for item in body] == ["user", "assistant"]
        assert body[0]["sequenceNo"] == 1
        assert body[1]["sequenceNo"] == 2
        assistant = next(item for item in body if item["role"] == "assistant")
        if len(assistant["uiParts"]) > 1:
            break
        time.sleep(0.05)

    assert assistant is not None
    types = [part["type"] for part in assistant["uiParts"]]
    assert "text" in types
    assert "reasoning" in types
    assert "tool-call" in types
    assert "data-chart" in types
    assert "data-table" in types
    assert assistant["contentBlocks"]
    assert assistant["traceSummary"]["stepCount"] == 1
    assert assistant["traceSummary"]["toolCallCount"] == 1
    assert assistant["traceSummary"]["status"] == "completed"
    assert assistant["finalText"]

    stream = client.get(f"/api/runs/{run_id}/stream?after_seq=0")
    assert stream.status_code == 200
    assert stream.headers["x-vercel-ai-ui-message-stream"] == "v1"
    content = stream.text
    assert "id: " in content
    assert '"kind": "snapshot"' in content
    assert '"kind": "part"' in content
    assert '"type": "start-step"' in content
    assert '"type": "finish"' in content
    assert '"kind": "done"' in content
    assert "[DONE]" in content


def test_first_prompt_updates_placeholder_conversation_title(client) -> None:
    conversation = client.post("/api/conversations", json={"skillId": "demo-analyst"}).json()
    assert conversation["title"] == "新建会话"

    first_prompt = "这个月哪个用户产生的销售额最多？"
    payload = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": first_prompt, "attachments": []},
    )
    assert payload.status_code == 200

    updated = client.get(f"/api/conversations/{conversation['id']}")
    assert updated.status_code == 200
    assert updated.json()["title"] == first_prompt


def test_stream_after_seq_filters_history(client) -> None:
    conversation = client.post("/api/conversations", json={"title": "恢复测试", "skillId": "demo-analyst"}).json()
    payload = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "请输出图表趋势", "attachments": []},
    ).json()
    process_next_run()

    all_events = client.get(f"/api/runs/{payload['runId']}/stream?after_seq=0").text
    assert '"kind": "snapshot"' in all_events
    assert '"seq": 1' in all_events

    later_events = client.get(f"/api/runs/{payload['runId']}/stream?after_seq=5").text
    assert '"kind": "snapshot"' not in later_events
    assert '"seq": 1,' not in later_events
    assert '"kind": "part"' in later_events
    assert "[DONE]" in later_events

    resumed_by_header = client.get(
        f"/api/runs/{payload['runId']}/stream",
        headers={"Last-Event-ID": "5"},
    ).text
    assert '"kind": "snapshot"' not in resumed_by_header
    assert '"seq": 1,' not in resumed_by_header
    assert "[DONE]" in resumed_by_header


def test_artifact_detail_route_returns_large_payload(monkeypatch) -> None:
    monkeypatch.setenv("ARTIFACT_INLINE_THRESHOLD_BYTES", "1")
    reset_settings_cache()
    reset_db_state()
    reset_skill_loader()
    reset_schema()
    loader = get_skill_loader()
    loader.reload()

    with TestClient(app) as local_client:
        conversation = local_client.post("/api/conversations", json={"title": "Artifact 测试", "skillId": "demo-analyst"}).json()
        payload = local_client.post(
            f"/api/conversations/{conversation['id']}/messages",
            json={"content": "请给我一个图表和表格", "attachments": []},
        ).json()

        process_next_run()

        messages = local_client.get(f"/api/conversations/{conversation['id']}/messages")
        assert messages.status_code == 200
        assistant = next(item for item in messages.json() if item["role"] == "assistant")
        artifact_part = next(item for item in assistant["uiParts"] if item["type"] == "data-artifact")

        artifact = local_client.get(f"/api/artifacts/{artifact_part['artifactId']}")
        assert artifact.status_code == 200
        body = artifact.json()
        assert body["id"] == artifact_part["artifactId"]
        assert body["contentJson"]["type"] in {"data-chart", "data-table"}
        assert body["artifactType"] in {"chart", "table"}


def test_simple_explanatory_prompt_does_not_force_tool_call(client) -> None:
    conversation = client.post("/api/conversations", json={"title": "解释测试", "skillId": "demo-analyst"}).json()
    payload = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "你是谁？你能做什么？", "attachments": []},
    ).json()

    process_next_run()

    messages = client.get(f"/api/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    assistant = next(item for item in messages.json() if item["role"] == "assistant")
    types = [part["type"] for part in assistant["uiParts"]]
    assert "text" in types
    assert "tool-call" not in types
    assert "reasoning" not in types
    assert "智能体" in assistant["finalText"]
    assert assistant["traceSummary"]["toolCallCount"] == 0
    assert assistant["traceSummary"]["hasReasoning"] is False
    assert assistant["traceSummary"]["status"] == "completed"

    stream = client.get(f"/api/runs/{payload['runId']}/stream?after_seq=0").text
    assert '"kind": "snapshot"' in stream
    assert '"kind": "done"' in stream


def test_multi_turn_follow_up_reuses_local_context(client) -> None:
    conversation = client.post("/api/conversations", json={"title": "多轮测试", "skillId": "demo-analyst"}).json()
    first = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "请给我最近七天订单趋势", "attachments": []},
    ).json()
    process_next_run()

    second = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "基于上一个回答，按月份看呢？", "attachments": []},
    ).json()
    process_next_run()

    messages = client.get(f"/api/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    body = messages.json()
    assistants = [item for item in body if item["role"] == "assistant"]
    assert [item["role"] for item in body] == ["user", "assistant", "user", "assistant"]
    assert [item["sequenceNo"] for item in body] == [1, 2, 3, 4]
    assert len(assistants) == 2
    latest = assistants[-1]
    assert "上一轮上下文" in latest["finalText"]
    assert latest["traceSummary"]["toolCallCount"] == 1
    assert latest["traceSummary"]["status"] == "completed"
    assert any(part["type"] == "data-table" for part in latest["uiParts"])

    with session_scope() as session:
        run = session.scalar(select(Run).where(Run.id == second["runId"]))
        assert run is not None
        assert "用户:" in run.context_json["conversationContext"]
        assert "助手:" in run.context_json["conversationContext"]
