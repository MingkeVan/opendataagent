from __future__ import annotations

import json
from collections import OrderedDict
from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.ids import new_id
from app.core.time import utcnow
from app.models.entities import Artifact, Conversation, Message, Run, RunEvent, SkillSnapshot, ToolCall
from app.services.skill_loader import get_skill_loader

TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "interrupted"}


def create_run(session: Session, conversation: Conversation, content: str) -> tuple[Message, Message, Run]:
    loader = get_skill_loader()
    snapshot = loader.get_or_create_snapshot(session, conversation.skill_id)
    now = utcnow()
    assistant_created_at = now + timedelta(microseconds=1)
    user_message = Message(
        id=new_id("msg"),
        conversation_id=conversation.id,
        run_id=None,
        role="user",
        raw_blocks=[{"type": "text", "text": content}],
        ui_parts=[{"type": "text", "text": content}],
        usage_json=None,
        status="completed",
        created_at=now,
        updated_at=now,
    )
    run = Run(
        id=new_id("run"),
        conversation_id=conversation.id,
        skill_snapshot_id=snapshot.id,
        engine="claude-agent-sdk",
        status="queued",
        created_at=now,
        updated_at=now,
    )
    assistant_message = Message(
        id=new_id("msg"),
        conversation_id=conversation.id,
        run_id=run.id,
        role="assistant",
        raw_blocks=[],
        ui_parts=[],
        usage_json=None,
        status="queued",
        created_at=assistant_created_at,
        updated_at=assistant_created_at,
    )
    conversation.status = "running"
    conversation.active_run_id = run.id
    conversation.last_message_at = now
    conversation.updated_at = now
    session.add_all([user_message, run, assistant_message])
    session.commit()
    session.refresh(user_message)
    session.refresh(assistant_message)
    session.refresh(run)
    return user_message, assistant_message, run


def get_run(session: Session, run_id: str) -> Run | None:
    return session.get(Run, run_id)


def get_assistant_message_for_run(session: Session, run_id: str) -> Message:
    return session.scalar(select(Message).where(Message.run_id == run_id, Message.role == "assistant"))


def get_skill_snapshot(session: Session, snapshot_id: str) -> SkillSnapshot:
    return session.get(SkillSnapshot, snapshot_id)


def get_conversation_messages(session: Session, conversation_id: str) -> list[Message]:
    return list(
        session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
    )


def get_last_user_prompt(session: Session, conversation_id: str) -> str:
    message = session.scalar(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.role == "user")
        .order_by(Message.created_at.desc())
    )
    if message is None:
        return ""
    for part in message.ui_parts:
        if part.get("type") == "text":
            return part.get("text", "")
    return ""


def claim_next_run(session: Session) -> Run | None:
    row = session.execute(
        text(
            "SELECT id FROM runs WHERE status = 'queued' "
            "ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED"
        )
    ).first()
    if row is None:
        return None
    run = session.get(Run, row[0])
    run.status = "running"
    run.started_at = utcnow()
    run.updated_at = utcnow()
    assistant_message = get_assistant_message_for_run(session, run.id)
    if assistant_message is not None:
        assistant_message.status = "streaming"
        assistant_message.updated_at = utcnow()
    conversation = session.get(Conversation, run.conversation_id)
    if conversation is not None:
        conversation.status = "running"
        conversation.active_run_id = run.id
        conversation.updated_at = utcnow()
    session.commit()
    session.refresh(run)
    return run


def get_latest_seq(session: Session, run_id: str) -> int:
    latest = session.scalar(select(func.max(RunEvent.seq)).where(RunEvent.run_id == run_id))
    return int(latest or 0)


def create_artifact(
    session: Session,
    run: Run,
    payload: dict,
    artifact_type: str,
    title: str,
) -> Artifact:
    serialized = json.dumps(payload, ensure_ascii=False)
    artifact = Artifact(
        id=new_id("art"),
        run_id=run.id,
        conversation_id=run.conversation_id,
        artifact_type=artifact_type,
        mime_type="application/json",
        size_bytes=len(serialized.encode("utf-8")),
        content_json=payload,
        content_text=None,
        metadata_json={"title": title},
    )
    session.add(artifact)
    session.flush()
    return artifact


def normalize_event_payload(session: Session, run: Run, payload: dict) -> dict:
    settings = get_settings()
    normalized = dict(payload)
    if normalized["type"] in {"data-chart", "data-table"}:
        serialized = json.dumps(normalized, ensure_ascii=False)
        if len(serialized.encode("utf-8")) > settings.artifact_inline_threshold_bytes:
            artifact = create_artifact(
                session,
                run,
                payload=normalized,
                artifact_type=normalized["type"].replace("data-", ""),
                title=normalized.get("title", normalized["type"]),
            )
            normalized = {
                "type": "data-artifact",
                "id": normalized.get("id", artifact.id),
                "artifactId": artifact.id,
                "artifactType": artifact.artifact_type,
                "title": normalized.get("title", artifact.artifact_type),
                "summary": normalized.get("summary", "大型结果已归档到 artifact"),
                "stepId": normalized.get("stepId"),
            }
    return normalized


def append_run_event(session: Session, run: Run, seq: int, payload: dict, raw_payload: dict | None = None) -> RunEvent:
    normalized = normalize_event_payload(session, run, payload)
    event = RunEvent(
        run_id=run.id,
        seq=seq,
        event_type=normalized["type"],
        payload_json=normalized,
        raw_payload_json=raw_payload,
        visible_in_history=True,
        created_at=utcnow(),
    )
    session.add(event)
    session.flush()
    _sync_tool_call_state(session, run, normalized)
    return event


def _sync_tool_call_state(session: Session, run: Run, payload: dict) -> None:
    event_type = payload["type"]
    if not event_type.startswith("tool-"):
        return
    tool_call_id = payload.get("toolCallId")
    if not tool_call_id:
        return
    tool_call = session.scalar(
        select(ToolCall).where(ToolCall.run_id == run.id, ToolCall.tool_call_id == tool_call_id)
    )
    if tool_call is None:
        tool_call = ToolCall(
            id=new_id("tool"),
            run_id=run.id,
            message_id=get_assistant_message_for_run(session, run.id).id,
            tool_call_id=tool_call_id,
            tool_name=payload.get("toolName", "tool"),
            input_json=None,
            output_summary=None,
            artifact_id=payload.get("artifactId"),
            status="input-streaming",
            created_at=utcnow(),
        )
        session.add(tool_call)
        session.flush()

    if event_type == "tool-input-start":
        tool_call.status = "input-streaming"
        tool_call.started_at = utcnow()
    elif event_type == "tool-input-available":
        tool_call.input_json = payload.get("input")
        tool_call.status = "input-ready"
    elif event_type == "tool-output-available":
        tool_call.output_summary = payload.get("output")
        tool_call.status = "output-ready"
        tool_call.ended_at = utcnow()
        if tool_call.started_at:
            tool_call.latency_ms = int((tool_call.ended_at - tool_call.started_at).total_seconds() * 1000)
    elif event_type == "tool-failed":
        tool_call.status = "failed"
        tool_call.error_message = payload.get("error")
        tool_call.ended_at = utcnow()


def list_run_events(session: Session, run_id: str, after_seq: int = 0) -> list[RunEvent]:
    return list(
        session.scalars(
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
            .order_by(RunEvent.seq.asc())
        )
    )


def aggregate_run_output(session: Session, run: Run) -> tuple[list[dict], list[dict]]:
    events = list_run_events(session, run.id, 0)
    texts: OrderedDict[str, dict] = OrderedDict()
    reasonings: OrderedDict[str, dict] = OrderedDict()
    tools: OrderedDict[str, dict] = OrderedDict()
    data_parts: list[dict] = []
    steps: OrderedDict[str, dict] = OrderedDict()

    for event in events:
        payload = event.payload_json
        event_type = payload["type"]
        if event_type == "text-start":
            texts[payload["id"]] = {"type": "text", "id": payload["id"], "text": "", "stepId": payload.get("stepId")}
        elif event_type == "text-delta":
            item = texts.setdefault(
                payload["id"], {"type": "text", "id": payload["id"], "text": "", "stepId": payload.get("stepId")}
            )
            item["text"] += payload.get("delta", "")
        elif event_type == "reasoning-start":
            reasonings[payload["id"]] = {
                "type": "reasoning",
                "id": payload["id"],
                "summary": "",
                "stepId": payload.get("stepId"),
            }
        elif event_type == "reasoning-delta":
            item = reasonings.setdefault(
                payload["id"],
                {"type": "reasoning", "id": payload["id"], "summary": "", "stepId": payload.get("stepId")},
            )
            item["summary"] += payload.get("delta", "")
        elif event_type == "tool-input-start":
            tools[payload["toolCallId"]] = {
                "type": "tool-call",
                "id": payload["toolCallId"],
                "toolName": payload.get("toolName"),
                "state": "input-streaming",
                "input": None,
                "output": None,
                "artifactId": payload.get("artifactId"),
                "stepId": payload.get("stepId"),
            }
        elif event_type == "tool-input-available":
            item = tools.setdefault(
                payload["toolCallId"],
                {
                    "type": "tool-call",
                    "id": payload["toolCallId"],
                    "toolName": payload.get("toolName"),
                    "state": "input-ready",
                    "input": None,
                    "output": None,
                    "artifactId": payload.get("artifactId"),
                    "stepId": payload.get("stepId"),
                },
            )
            item["input"] = payload.get("input")
            item["state"] = "input-ready"
        elif event_type == "tool-output-available":
            item = tools.setdefault(
                payload["toolCallId"],
                {
                    "type": "tool-call",
                    "id": payload["toolCallId"],
                    "toolName": payload.get("toolName"),
                    "state": "running",
                    "input": None,
                    "output": None,
                    "artifactId": payload.get("artifactId"),
                    "stepId": payload.get("stepId"),
                },
            )
            item["output"] = payload.get("output")
            item["state"] = "output-ready"
        elif event_type == "tool-failed":
            item = tools.setdefault(
                payload["toolCallId"],
                {
                    "type": "tool-call",
                    "id": payload["toolCallId"],
                    "toolName": payload.get("toolName"),
                    "state": "failed",
                    "input": None,
                    "output": None,
                    "artifactId": payload.get("artifactId"),
                    "stepId": payload.get("stepId"),
                },
            )
            item["error"] = payload.get("error")
            item["state"] = "failed"
        elif event_type in {"data-chart", "data-table", "data-artifact"}:
            data_parts.append(payload)
        elif event_type == "finish-step":
            steps[payload["stepId"]] = {
                "type": "step",
                "stepId": payload["stepId"],
                "title": payload.get("title", "执行步骤"),
                "status": "completed",
            }

    ui_parts: list[dict] = []
    ui_parts.extend(list(steps.values()))
    ui_parts.extend(list(reasonings.values()))
    ui_parts.extend(list(tools.values()))
    ui_parts.extend(data_parts)
    ui_parts.extend(list(texts.values()))

    raw_blocks: list[dict] = []
    for reasoning in reasonings.values():
        raw_blocks.append(
            {
                "type": "thinking",
                "thinking": reasoning["summary"],
                "signature": f"mock-signature-{reasoning['id']}",
            }
        )
    for tool in tools.values():
        raw_blocks.append(
            {
                "type": "tool_use",
                "id": tool["id"],
                "name": tool["toolName"],
                "input": tool.get("input") or {},
            }
        )
        raw_blocks.append(
            {
                "type": "tool_result",
                "tool_use_id": tool["id"],
                "content": tool.get("output") or {"artifactId": tool.get("artifactId")},
            }
        )
    combined_text = "\n".join(part["text"] for part in texts.values() if part["text"]).strip()
    if combined_text:
        raw_blocks.append({"type": "text", "text": combined_text})
    return ui_parts, raw_blocks


def complete_run(session: Session, run: Run, stop_reason: str = "completed") -> None:
    ui_parts, raw_blocks = aggregate_run_output(session, run)
    assistant_message = get_assistant_message_for_run(session, run.id)
    assistant_message.ui_parts = ui_parts
    assistant_message.raw_blocks = raw_blocks
    assistant_message.status = "completed" if stop_reason == "completed" else stop_reason
    assistant_message.updated_at = utcnow()
    run.status = stop_reason
    run.stop_reason = stop_reason
    run.ended_at = utcnow()
    run.updated_at = utcnow()
    conversation = session.get(Conversation, run.conversation_id)
    conversation.status = "idle" if stop_reason == "completed" else stop_reason
    conversation.active_run_id = None
    conversation.last_message_at = utcnow()
    conversation.updated_at = utcnow()


def fail_run(session: Session, run: Run, status: str, error_code: str | None, error_message: str | None) -> None:
    assistant_message = get_assistant_message_for_run(session, run.id)
    if assistant_message is not None:
        assistant_message.status = status
        assistant_message.updated_at = utcnow()
    run.status = status
    run.error_code = error_code
    run.error_message = error_message
    run.stop_reason = status
    run.ended_at = utcnow()
    run.updated_at = utcnow()
    conversation = session.get(Conversation, run.conversation_id)
    if conversation is not None:
        conversation.status = "idle" if status == "cancelled" else status
        conversation.active_run_id = None
        conversation.updated_at = utcnow()
