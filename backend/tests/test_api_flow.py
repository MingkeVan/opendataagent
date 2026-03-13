from __future__ import annotations

import time

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

    stream = client.get(f"/api/runs/{run_id}/stream?after_seq=0")
    assert stream.status_code == 200
    content = stream.text
    assert '"type": "start-step"' in content
    assert '"type": "finish"' in content
    assert "[DONE]" in content


def test_stream_after_seq_filters_history(client) -> None:
    conversation = client.post("/api/conversations", json={"title": "恢复测试", "skillId": "demo-analyst"}).json()
    payload = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "请输出图表趋势", "attachments": []},
    ).json()
    process_next_run()

    all_events = client.get(f"/api/runs/{payload['runId']}/stream?after_seq=0").text
    assert '"seq": 1,' in all_events

    later_events = client.get(f"/api/runs/{payload['runId']}/stream?after_seq=5").text
    assert '"seq": 1,' not in later_events
    assert '"seq": 6,' in later_events
    assert "[DONE]" in later_events
