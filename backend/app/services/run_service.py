from __future__ import annotations

import json
from collections import OrderedDict, defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.ids import new_id
from app.core.time import utcnow
from app.models.entities import (
    Artifact,
    Conversation,
    Message,
    MessageBlock,
    Run,
    RunEvent,
    RunStep,
    SkillSnapshot,
    ToolCall,
)
from app.services.skill_loader import get_skill_loader

TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "interrupted"}


def chunk_text(text: str, size: int = 22) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)] or [text]


def build_table_title(prompt: str, index: int) -> str:
    cleaned = prompt.strip().rstrip("？?")
    if not cleaned:
        return f"查询结果 {index}"
    return cleaned if len(cleaned) <= 24 else f"{cleaned[:24]}..."


def wants_chart(prompt: str) -> bool:
    return any(keyword in prompt for keyword in ["图", "趋势", "走势", "变化", "按天", "按月", "chart", "graph"])


def maybe_build_chart(prompt: str, columns: list[str], rows: list[list[object | None]], step_id: str, step_index: int) -> dict | None:
    if not wants_chart(prompt) or len(columns) < 2 or not rows:
        return None
    y_values = [row[1] for row in rows]
    if not all(isinstance(value, (int, float)) for value in y_values):
        return None
    return {
        "type": "data-chart",
        "id": new_id("chart"),
        "title": f"{build_table_title(prompt, step_index)} 趋势",
        "chartType": "line",
        "spec": {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": [row[0] for row in rows]},
            "yAxis": {"type": "value"},
            "series": [{"type": "line", "smooth": True, "data": y_values}],
        },
        "summary": f"基于 {len(rows)} 个数据点生成趋势图。",
        "stepId": step_id,
        "stepIndex": step_index,
    }


def summarize_reasoning(text: str, max_length: int = 280) -> str:
    compact = " ".join((text or "").replace("```", " ").split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 1].rstrip()}…"


def merge_dict(base: dict[str, Any] | None, updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def create_run(
    session: Session,
    conversation: Conversation,
    content: str,
    attachments: list[dict[str, Any]] | None = None,
) -> tuple[Message, Message, Run]:
    loader = get_skill_loader()
    snapshot = loader.get_or_create_snapshot(session, conversation.skill_id)
    now = utcnow()
    assistant_created_at = now + timedelta(microseconds=1)

    user_blocks = [{"type": "text", "text": content}]
    user_message = Message(
        id=new_id("msg"),
        conversation_id=conversation.id,
        run_id=None,
        role="user",
        raw_blocks=None,
        ui_parts=[{"type": "text", "text": content}],
        content_blocks=user_blocks,
        trace_summary={"stepCount": 0, "toolCallCount": 0, "hasReasoning": False},
        final_text=content,
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
        context_json={
            "currentPrompt": content,
            "userAttachments": attachments or [],
            "skillId": snapshot.skill_id,
            "skillVersion": snapshot.skill_version,
        },
        created_at=now,
        updated_at=now,
    )
    assistant_message = Message(
        id=new_id("msg"),
        conversation_id=conversation.id,
        run_id=run.id,
        role="assistant",
        raw_blocks=None,
        ui_parts=[],
        content_blocks=[],
        trace_summary=None,
        final_text=None,
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
    session.flush()
    append_message_block(
        session,
        user_message,
        block_type="text",
        payload={"type": "text", "text": content},
        role="user",
        visibility="user",
    )
    session.commit()
    session.refresh(user_message)
    session.refresh(assistant_message)
    session.refresh(run)
    return user_message, assistant_message, run


def get_run(session: Session, run_id: str) -> Run | None:
    return session.get(Run, run_id)


def get_assistant_message_for_run(session: Session, run_id: str) -> Message | None:
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
    return extract_message_text(message)


def extract_message_text(message: Message) -> str:
    if message.final_text:
        return message.final_text
    for part in message.ui_parts or []:
        if part.get("type") == "text":
            return str(part.get("text", ""))
    return ""


def build_conversation_context(session: Session, conversation_id: str, current_run_id: str | None = None) -> str:
    lines: list[str] = []
    for message in get_conversation_messages(session, conversation_id):
        if message.role == "assistant" and message.run_id == current_run_id:
            continue
        text = extract_message_text(message).strip()
        if not text:
            continue
        role = "用户" if message.role == "user" else "助手"
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


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


def get_latest_block_index(session: Session, message_id: str) -> int:
    latest = session.scalar(select(func.max(MessageBlock.block_index)).where(MessageBlock.message_id == message_id))
    return int(latest or 0)


def get_latest_run_step(session: Session, run_id: str) -> RunStep | None:
    return session.scalar(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.step_index.desc()))


def list_run_steps(session: Session, run_id: str) -> list[RunStep]:
    return list(session.scalars(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.step_index.asc())))


def list_message_blocks(session: Session, message_id: str) -> list[MessageBlock]:
    return list(
        session.scalars(
            select(MessageBlock).where(MessageBlock.message_id == message_id).order_by(MessageBlock.block_index.asc())
        )
    )


def parse_step_index(raw_step_id: str | None, raw_step_index: int | None = None) -> int:
    if raw_step_index is not None:
        return raw_step_index
    if raw_step_id and raw_step_id.rsplit("_", 1)[-1].isdigit():
        return int(raw_step_id.rsplit("_", 1)[-1])
    return 1


def step_identifier(step_index: int, raw_step_id: str | None = None) -> str:
    return raw_step_id or f"step_{step_index}"


def append_message_block(
    session: Session,
    message: Message,
    block_type: str,
    payload: dict[str, Any],
    role: str,
    visibility: str,
    *,
    step_index: int | None = None,
    tool_call_id: str | None = None,
    raw_provider_json: dict[str, Any] | None = None,
) -> MessageBlock:
    block = MessageBlock(
        id=new_id("blk"),
        message_id=message.id,
        conversation_id=message.conversation_id,
        run_id=message.run_id,
        role=role,
        step_index=step_index,
        block_index=get_latest_block_index(session, message.id) + 1,
        block_type=block_type,
        tool_call_id=tool_call_id,
        visibility=visibility,
        payload_json=payload,
        raw_provider_json=raw_provider_json,
        created_at=utcnow(),
    )
    session.add(block)
    session.flush()
    return block


def get_or_create_run_step(
    session: Session,
    run: Run,
    *,
    step_index: int,
    step_id: str,
    title: str | None = None,
    model: str | None = None,
) -> RunStep:
    step = session.scalar(select(RunStep).where(RunStep.run_id == run.id, RunStep.step_index == step_index))
    if step is None:
        now = utcnow()
        step = RunStep(
            id=new_id("step"),
            run_id=run.id,
            step_index=step_index,
            step_id=step_id,
            title=title,
            status="running",
            model=model,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(step)
        session.flush()
        return step
    if title:
        step.title = title
    if model:
        step.model = model
    step.updated_at = utcnow()
    return step


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


def normalize_stream_part(session: Session, run: Run, payload: dict) -> dict:
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
                "stepIndex": normalized.get("stepIndex"),
                "toolCallId": normalized.get("toolCallId"),
            }
    return normalized


def build_stream_envelope(
    run: Run,
    seq: int,
    kind: str,
    payload: dict[str, Any],
    *,
    message_id: str | None,
    step_index: int | None,
    part_id: str | None,
) -> dict[str, Any]:
    return {
        "version": "v2",
        "kind": kind,
        "runId": run.id,
        "messageId": message_id,
        "seq": seq,
        "stepIndex": step_index,
        "partId": part_id,
        "payload": payload,
    }


def append_run_event(session: Session, run: Run, seq: int, payload: dict, raw_payload: dict | None = None) -> RunEvent:
    assistant_message = get_assistant_message_for_run(session, run.id)
    normalized = normalize_stream_part(session, run, payload)
    envelope = build_stream_envelope(
        run,
        seq,
        "part",
        normalized,
        message_id=assistant_message.id if assistant_message is not None else None,
        step_index=normalized.get("stepIndex"),
        part_id=str(normalized.get("id") or normalized.get("toolCallId") or normalized.get("stepId") or f"part_{seq}"),
    )
    event = RunEvent(
        run_id=run.id,
        seq=seq,
        event_type=normalized["type"],
        payload_json=envelope,
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
    assistant_message = get_assistant_message_for_run(session, run.id)
    tool_call = session.scalar(
        select(ToolCall).where(ToolCall.run_id == run.id, ToolCall.tool_call_id == tool_call_id)
    )
    if tool_call is None:
        tool_call = ToolCall(
            id=new_id("tool"),
            run_id=run.id,
            message_id=assistant_message.id if assistant_message is not None else None,
            step_index=payload.get("stepIndex"),
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

    tool_call.step_index = payload.get("stepIndex", tool_call.step_index)
    tool_call.tool_name = payload.get("toolName", tool_call.tool_name)
    if payload.get("artifactId"):
        tool_call.artifact_id = payload["artifactId"]

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


def update_run_context(run: Run, updates: dict[str, Any]) -> None:
    run.context_json = merge_dict(run.context_json, updates)
    run.updated_at = utcnow()


def summarize_tool_record(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("error"):
        return {"database": record.get("database"), "error": record["error"]}
    return {
        "database": record.get("database"),
        "rowCount": len(record.get("rows", [])),
        "columns": record.get("columns", []),
        "truncated": bool(record.get("truncated")),
    }


def project_tool_record_parts(run: Run, step_id: str, step_index: int, tool_call_id: str, record: dict[str, Any]) -> list[dict]:
    prompt = str((run.context_json or {}).get("currentPrompt") or "")
    if record.get("error"):
        return []
    columns = list(record.get("columns", []))
    rows = list(record.get("rows", []))
    table_part = {
        "type": "data-table",
        "id": new_id("table"),
        "title": build_table_title(prompt, step_index),
        "columns": columns,
        "rows": rows,
        "summary": f"返回 {len(rows)} 行结果，字段为 {', '.join(columns)}。" if columns else f"返回 {len(rows)} 行结果。",
        "stepId": step_id,
        "stepIndex": step_index,
        "toolCallId": tool_call_id,
    }
    chart_part = maybe_build_chart(prompt, columns, rows, step_id, step_index)
    if chart_part is not None:
        chart_part["toolCallId"] = tool_call_id
        return [table_part, chart_part]
    return [table_part]


def process_agent_event(session: Session, run: Run, seq: int, raw_event: dict[str, Any]) -> int:
    event_type = raw_event["type"]
    assistant_message = get_assistant_message_for_run(session, run.id)
    if assistant_message is None:
        raise RuntimeError("Assistant message not found for run")

    if event_type == "run-context":
        update_run_context(run, raw_event.get("context", {}))
        return seq

    if event_type == "step-start":
        step_index = parse_step_index(raw_event.get("stepId"), raw_event.get("stepIndex"))
        step_id = step_identifier(step_index, raw_event.get("stepId"))
        get_or_create_run_step(
            session,
            run,
            step_index=step_index,
            step_id=step_id,
            title=raw_event.get("title"),
            model=raw_event.get("model"),
        )
        seq += 1
        append_run_event(
            session,
            run,
            seq,
            {"type": "start-step", "stepId": step_id, "stepIndex": step_index, "title": raw_event.get("title", "执行步骤")},
            raw_event,
        )
        return seq

    if event_type == "assistant-message":
        step_index = parse_step_index(raw_event.get("stepId"), raw_event.get("stepIndex"))
        step_id = step_identifier(step_index, raw_event.get("stepId"))
        get_or_create_run_step(
            session,
            run,
            step_index=step_index,
            step_id=step_id,
            title=raw_event.get("title"),
            model=raw_event.get("model"),
        )
        for block in raw_event.get("blocks", []):
            block_type = block["type"]
            if block_type == "thinking":
                summary = summarize_reasoning(str(block.get("thinking") or ""))
                append_message_block(
                    session,
                    assistant_message,
                    block_type="thinking",
                    payload={
                        "type": "thinking",
                        "thinking": block.get("thinking", ""),
                        "summary": summary,
                        "stepId": step_id,
                        "stepIndex": step_index,
                    },
                    role="assistant",
                    visibility="internal",
                    step_index=step_index,
                    raw_provider_json=block,
                )
                reasoning_id = f"reasoning_{step_index}"
                seq += 1
                append_run_event(
                    session,
                    run,
                    seq,
                    {"type": "reasoning-start", "id": reasoning_id, "stepId": step_id, "stepIndex": step_index},
                    block,
                )
                for chunk in chunk_text(summary or "思考中..."):
                    seq += 1
                    append_run_event(
                        session,
                        run,
                        seq,
                        {
                            "type": "reasoning-delta",
                            "id": reasoning_id,
                            "delta": chunk,
                            "stepId": step_id,
                            "stepIndex": step_index,
                        },
                        block,
                    )
                seq += 1
                append_run_event(
                    session,
                    run,
                    seq,
                    {"type": "reasoning-end", "id": reasoning_id, "stepId": step_id, "stepIndex": step_index},
                    block,
                )
            elif block_type == "tool_use":
                tool_call_id = str(block.get("id") or new_id("toolcall"))
                append_message_block(
                    session,
                    assistant_message,
                    block_type="tool_use",
                    payload={
                        "type": "tool_use",
                        "id": tool_call_id,
                        "name": block.get("name"),
                        "input": block.get("input") or {},
                        "stepId": step_id,
                        "stepIndex": step_index,
                    },
                    role="assistant",
                    visibility="trace",
                    step_index=step_index,
                    tool_call_id=tool_call_id,
                    raw_provider_json=block,
                )
                seq += 1
                append_run_event(
                    session,
                    run,
                    seq,
                    {
                        "type": "tool-input-start",
                        "toolCallId": tool_call_id,
                        "toolName": block.get("name"),
                        "stepId": step_id,
                        "stepIndex": step_index,
                    },
                    block,
                )
                input_payload = block.get("input") or {}
                seq += 1
                append_run_event(
                    session,
                    run,
                    seq,
                    {
                        "type": "tool-input-delta",
                        "toolCallId": tool_call_id,
                        "toolName": block.get("name"),
                        "delta": json.dumps(input_payload, ensure_ascii=False),
                        "stepId": step_id,
                        "stepIndex": step_index,
                    },
                    block,
                )
                seq += 1
                append_run_event(
                    session,
                    run,
                    seq,
                    {
                        "type": "tool-input-available",
                        "toolCallId": tool_call_id,
                        "toolName": block.get("name"),
                        "input": input_payload,
                        "stepId": step_id,
                        "stepIndex": step_index,
                    },
                    block,
                )
            elif block_type == "tool_result":
                tool_call_id = str(block.get("tool_use_id") or new_id("toolcall"))
                append_message_block(
                    session,
                    assistant_message,
                    block_type="tool_result",
                    payload={
                        "type": "tool_result",
                        "toolUseId": tool_call_id,
                        "content": block.get("content"),
                        "stepId": step_id,
                        "stepIndex": step_index,
                    },
                    role="assistant",
                    visibility="trace",
                    step_index=step_index,
                    tool_call_id=tool_call_id,
                    raw_provider_json=block,
                )
            elif block_type == "text":
                text_id = f"text_{step_index}"
                text_value = str(block.get("text") or "")
                append_message_block(
                    session,
                    assistant_message,
                    block_type="text",
                    payload={
                        "type": "text",
                        "id": text_id,
                        "text": text_value,
                        "stepId": step_id,
                        "stepIndex": step_index,
                    },
                    role="assistant",
                    visibility="user",
                    step_index=step_index,
                    raw_provider_json=block,
                )
                seq += 1
                append_run_event(
                    session,
                    run,
                    seq,
                    {"type": "text-start", "id": text_id, "stepId": step_id, "stepIndex": step_index},
                    block,
                )
                for chunk in chunk_text(text_value):
                    seq += 1
                    append_run_event(
                        session,
                        run,
                        seq,
                        {
                            "type": "text-delta",
                            "id": text_id,
                            "delta": chunk,
                            "stepId": step_id,
                            "stepIndex": step_index,
                        },
                        block,
                    )
                seq += 1
                append_run_event(
                    session,
                    run,
                    seq,
                    {"type": "text-end", "id": text_id, "stepId": step_id, "stepIndex": step_index},
                    block,
                )
        return seq

    if event_type == "tool-result":
        step_index = parse_step_index(raw_event.get("stepId"), raw_event.get("stepIndex"))
        step_id = step_identifier(step_index, raw_event.get("stepId"))
        get_or_create_run_step(
            session,
            run,
            step_index=step_index,
            step_id=step_id,
            title=raw_event.get("title"),
            model=raw_event.get("model"),
        )
        record = dict(raw_event.get("record") or {})
        tool_call_id = str(raw_event.get("toolCallId") or new_id("toolcall"))
        tool_name = str(raw_event.get("toolName") or "tool")
        append_message_block(
            session,
            assistant_message,
            block_type="tool_result",
            payload={
                "type": "tool_result",
                "toolUseId": tool_call_id,
                "toolName": tool_name,
                "record": record,
                "stepId": step_id,
                "stepIndex": step_index,
            },
            role="assistant",
            visibility="trace",
            step_index=step_index,
            tool_call_id=tool_call_id,
            raw_provider_json=raw_event,
        )
        if record.get("error"):
            seq += 1
            append_run_event(
                session,
                run,
                seq,
                {
                    "type": "tool-failed",
                    "toolCallId": tool_call_id,
                    "toolName": tool_name,
                    "error": record["error"],
                    "stepId": step_id,
                    "stepIndex": step_index,
                },
                raw_event,
            )
            return seq

        seq += 1
        append_run_event(
            session,
            run,
            seq,
            {
                "type": "tool-output-available",
                "toolCallId": tool_call_id,
                "toolName": tool_name,
                "output": summarize_tool_record(record),
                "stepId": step_id,
                "stepIndex": step_index,
            },
            raw_event,
        )
        for projected in project_tool_record_parts(run, step_id, step_index, tool_call_id, record):
            normalized = normalize_stream_part(session, run, projected)
            append_message_block(
                session,
                assistant_message,
                block_type="data_ref",
                payload=normalized,
                role="assistant",
                visibility="user",
                step_index=step_index,
                tool_call_id=tool_call_id,
                raw_provider_json=raw_event,
            )
            seq += 1
            append_run_event(session, run, seq, normalized, raw_event)
        return seq

    if event_type == "step-end":
        step_index = parse_step_index(raw_event.get("stepId"), raw_event.get("stepIndex"))
        step_id = step_identifier(step_index, raw_event.get("stepId"))
        step = get_or_create_run_step(
            session,
            run,
            step_index=step_index,
            step_id=step_id,
            title=raw_event.get("title"),
            model=raw_event.get("model"),
        )
        step.status = "completed"
        step.stop_reason = raw_event.get("stopReason", "completed")
        step.ended_at = utcnow()
        step.updated_at = utcnow()
        seq += 1
        append_run_event(
            session,
            run,
            seq,
            {
                "type": "finish-step",
                "stepId": step_id,
                "stepIndex": step_index,
                "title": raw_event.get("title", step.title or "执行步骤"),
            },
            raw_event,
        )
        return seq

    if event_type == "result":
        latest_step = get_latest_run_step(session, run.id)
        if latest_step is not None:
            latest_step.agent_session_id = raw_event.get("sessionId") or latest_step.agent_session_id
            latest_step.model = raw_event.get("model") or latest_step.model
            latest_step.usage_json = raw_event.get("usage") or latest_step.usage_json
            latest_step.stop_reason = raw_event.get("stopReason") or latest_step.stop_reason
            latest_step.updated_at = utcnow()
        update_run_context(
            run,
            {
                "result": {
                    "sessionId": raw_event.get("sessionId"),
                    "isError": raw_event.get("isError", False),
                    "result": raw_event.get("result"),
                    "model": raw_event.get("model"),
                    "usage": raw_event.get("usage"),
                }
            },
        )
        if raw_event.get("isError"):
            raise RuntimeError(str(raw_event.get("result") or "Claude Agent SDK returned an error"))
        return seq

    if event_type == "finish":
        seq += 1
        append_run_event(session, run, seq, {"type": "finish"}, raw_event)
        return seq

    raise RuntimeError(f"Unsupported agent event type: {event_type}")


def build_stream_ui_parts(events: list[RunEvent]) -> list[dict]:
    texts: OrderedDict[str, dict] = OrderedDict()
    reasonings: OrderedDict[str, dict] = OrderedDict()
    tools: OrderedDict[str, dict] = OrderedDict()
    data_parts: list[dict] = []
    steps: OrderedDict[str, dict] = OrderedDict()

    for event in events:
        payload = event.payload_json.get("payload", {})
        event_type = payload.get("type")
        if event_type == "start-step":
            steps[payload["stepId"]] = {
                "type": "step",
                "stepId": payload["stepId"],
                "stepIndex": payload.get("stepIndex"),
                "title": payload.get("title", "执行步骤"),
                "status": "running",
            }
        elif event_type == "finish-step":
            steps[payload["stepId"]] = {
                "type": "step",
                "stepId": payload["stepId"],
                "stepIndex": payload.get("stepIndex"),
                "title": payload.get("title", "执行步骤"),
                "status": "completed",
            }
        elif event_type == "reasoning-start":
            reasonings[payload["id"]] = {
                "type": "reasoning",
                "id": payload["id"],
                "summary": "",
                "displayHint": "collapsed",
                "stepId": payload.get("stepId"),
                "stepIndex": payload.get("stepIndex"),
            }
        elif event_type == "reasoning-delta":
            item = reasonings.setdefault(
                payload["id"],
                {
                    "type": "reasoning",
                    "id": payload["id"],
                    "summary": "",
                    "displayHint": "collapsed",
                    "stepId": payload.get("stepId"),
                    "stepIndex": payload.get("stepIndex"),
                },
            )
            item["summary"] += payload.get("delta", "")
        elif event_type == "text-start":
            texts[payload["id"]] = {
                "type": "text",
                "id": payload["id"],
                "text": "",
                "stepId": payload.get("stepId"),
                "stepIndex": payload.get("stepIndex"),
            }
        elif event_type == "text-delta":
            item = texts.setdefault(
                payload["id"],
                {
                    "type": "text",
                    "id": payload["id"],
                    "text": "",
                    "stepId": payload.get("stepId"),
                    "stepIndex": payload.get("stepIndex"),
                },
            )
            item["text"] += payload.get("delta", "")
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
                "stepIndex": payload.get("stepIndex"),
            }
        elif event_type == "tool-input-delta":
            item = tools.setdefault(
                payload["toolCallId"],
                {
                    "type": "tool-call",
                    "id": payload["toolCallId"],
                    "toolName": payload.get("toolName"),
                    "state": "input-streaming",
                    "input": None,
                    "output": None,
                    "artifactId": payload.get("artifactId"),
                    "stepId": payload.get("stepId"),
                    "stepIndex": payload.get("stepIndex"),
                },
            )
            item["inputText"] = f"{item.get('inputText', '')}{payload.get('delta', '')}"
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
                    "stepIndex": payload.get("stepIndex"),
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
                    "stepIndex": payload.get("stepIndex"),
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
                    "stepIndex": payload.get("stepIndex"),
                },
            )
            item["error"] = payload.get("error")
            item["state"] = "failed"
        elif event_type in {"data-chart", "data-table", "data-artifact"}:
            data_parts.append(payload)

    ui_parts: list[dict] = []
    step_ids = list(steps.keys())
    if step_ids:
        for step_id in step_ids:
            ui_parts.append(steps[step_id])
            ui_parts.extend([item for item in reasonings.values() if item.get("stepId") == step_id])
            ui_parts.extend([item for item in tools.values() if item.get("stepId") == step_id])
            ui_parts.extend([item for item in data_parts if item.get("stepId") == step_id])
            ui_parts.extend([item for item in texts.values() if item.get("stepId") == step_id])
    else:
        ui_parts.extend(list(reasonings.values()))
        ui_parts.extend(list(tools.values()))
        ui_parts.extend(data_parts)
        ui_parts.extend(list(texts.values()))
    return ui_parts


def build_message_projection(session: Session, run: Run) -> tuple[list[dict], list[dict], str, dict[str, Any]]:
    assistant_message = get_assistant_message_for_run(session, run.id)
    if assistant_message is None:
        return [], [], "", {"stepCount": 0, "toolCallCount": 0, "hasReasoning": False, "status": run.status}

    steps = list_run_steps(session, run.id)
    blocks = list_message_blocks(session, assistant_message.id)
    tool_calls = list(
        session.scalars(select(ToolCall).where(ToolCall.run_id == run.id).order_by(ToolCall.step_index.asc(), ToolCall.created_at.asc()))
    )

    step_parts: dict[int, dict[str, Any]] = {}
    for step in steps:
        step_parts[step.step_index] = {
            "type": "step",
            "stepId": step.step_id,
            "stepIndex": step.step_index,
            "title": step.title or "执行步骤",
            "status": "completed" if step.status == "completed" else step.status,
        }

    reasoning_parts: dict[int, dict[str, Any]] = {}
    text_parts: dict[int, dict[str, Any]] = {}
    data_parts: dict[int, list[dict[str, Any]]] = defaultdict(list)
    public_blocks: list[dict[str, Any]] = []

    for block in blocks:
        payload = dict(block.payload_json or {})
        if block.block_type == "thinking":
            step_index = int(block.step_index or 1)
            item = reasoning_parts.setdefault(
                step_index,
                {
                    "type": "reasoning",
                    "id": f"reasoning_{step_index}",
                    "summary": "",
                    "displayHint": "collapsed",
                    "stepId": payload.get("stepId") or step_parts.get(step_index, {}).get("stepId"),
                    "stepIndex": step_index,
                },
            )
            summary = str(payload.get("summary") or "")
            item["summary"] = f"{item['summary']}\n{summary}".strip() if item["summary"] else summary
            public_blocks.append(
                {
                    "type": "thinking",
                    "summary": summary,
                    "stepIndex": step_index,
                    "visibility": "collapsed",
                }
            )
        elif block.block_type == "tool_use":
            public_blocks.append(
                {
                    "type": "tool_use",
                    "id": payload.get("id"),
                    "name": payload.get("name"),
                    "input": payload.get("input"),
                    "stepIndex": block.step_index,
                }
            )
        elif block.block_type == "tool_result":
            public_blocks.append(
                {
                    "type": "tool_result",
                    "toolUseId": payload.get("toolUseId"),
                    "toolName": payload.get("toolName"),
                    "summary": summarize_tool_record(payload.get("record", {})) if payload.get("record") else payload.get("content"),
                    "stepIndex": block.step_index,
                }
            )
        elif block.block_type == "data_ref":
            data_parts[int(block.step_index or 1)].append(payload)
            public_blocks.append(
                {
                    "type": "data_ref",
                    "dataType": payload.get("type"),
                    "artifactId": payload.get("artifactId"),
                    "title": payload.get("title"),
                    "summary": payload.get("summary"),
                    "stepIndex": block.step_index,
                }
            )
        elif block.block_type == "text":
            step_index = int(block.step_index or 1)
            item = text_parts.setdefault(
                step_index,
                {
                    "type": "text",
                    "id": payload.get("id") or f"text_{step_index}",
                    "text": "",
                    "stepId": payload.get("stepId") or step_parts.get(step_index, {}).get("stepId"),
                    "stepIndex": step_index,
                },
            )
            item["text"] = f"{item['text']}\n{payload.get('text', '')}".strip() if item["text"] else str(payload.get("text", ""))
            public_blocks.append(
                {
                    "type": "text",
                    "text": payload.get("text", ""),
                    "stepIndex": step_index,
                }
            )

    tool_parts: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for tool_call in tool_calls:
        tool_parts[int(tool_call.step_index or 1)].append(
            {
                "type": "tool-call",
                "id": tool_call.tool_call_id,
                "toolName": tool_call.tool_name,
                "state": tool_call.status,
                "input": tool_call.input_json,
                "output": tool_call.output_summary,
                "artifactId": tool_call.artifact_id,
                "error": tool_call.error_message,
                "stepIndex": tool_call.step_index,
                "stepId": step_parts.get(int(tool_call.step_index or 1), {}).get("stepId"),
            }
        )

    ui_parts: list[dict[str, Any]] = []
    ordered_steps = sorted(set([*step_parts.keys(), *reasoning_parts.keys(), *text_parts.keys(), *data_parts.keys(), *tool_parts.keys()]))
    for step_index in ordered_steps:
        if step_index in step_parts:
            ui_parts.append(step_parts[step_index])
        if step_index in reasoning_parts:
            ui_parts.append(reasoning_parts[step_index])
        ui_parts.extend(tool_parts.get(step_index, []))
        ui_parts.extend(data_parts.get(step_index, []))
        if step_index in text_parts:
            ui_parts.append(text_parts[step_index])

    final_text = "\n\n".join(text_part["text"] for _, text_part in sorted(text_parts.items()) if text_part["text"]).strip()
    trace_summary = {
        "stepCount": len(step_parts),
        "toolCallCount": len(tool_calls),
        "hasReasoning": bool(reasoning_parts),
        "status": run.status,
        "agentSessionId": next((step.agent_session_id for step in reversed(steps) if step.agent_session_id), None),
    }
    return ui_parts, public_blocks, final_text, trace_summary


def build_stream_snapshot(session: Session, run: Run) -> dict[str, Any]:
    assistant_message = get_assistant_message_for_run(session, run.id)
    events = list_run_events(session, run.id, 0)
    latest_seq = events[-1].seq if events else 0
    ui_parts = build_stream_ui_parts(events)
    trace_summary = assistant_message.trace_summary if assistant_message is not None else None
    final_text = assistant_message.final_text if assistant_message is not None else None
    return {
        "uiParts": ui_parts,
        "traceSummary": trace_summary
        or {
            "stepCount": len([part for part in ui_parts if part.get("type") == "step"]),
            "toolCallCount": len([part for part in ui_parts if part.get("type") == "tool-call"]),
            "hasReasoning": any(part.get("type") == "reasoning" for part in ui_parts),
            "status": run.status,
        },
        "finalText": final_text,
        "latestSeq": latest_seq,
    }


def complete_run(session: Session, run: Run, stop_reason: str = "completed") -> None:
    ui_parts, content_blocks, final_text, trace_summary = build_message_projection(session, run)
    assistant_message = get_assistant_message_for_run(session, run.id)
    if assistant_message is not None:
        assistant_message.ui_parts = ui_parts
        assistant_message.content_blocks = content_blocks
        assistant_message.trace_summary = trace_summary
        assistant_message.final_text = final_text or None
        assistant_message.raw_blocks = None
        assistant_message.status = "completed" if stop_reason == "completed" else stop_reason
        assistant_message.updated_at = utcnow()
    run.status = stop_reason
    run.stop_reason = stop_reason
    run.ended_at = utcnow()
    run.updated_at = utcnow()
    conversation = session.get(Conversation, run.conversation_id)
    if conversation is not None:
        conversation.status = "idle" if stop_reason == "completed" else stop_reason
        conversation.active_run_id = None
        conversation.last_message_at = utcnow()
        conversation.updated_at = utcnow()


def fail_run(session: Session, run: Run, status: str, error_code: str | None, error_message: str | None) -> None:
    ui_parts, content_blocks, final_text, trace_summary = build_message_projection(session, run)
    assistant_message = get_assistant_message_for_run(session, run.id)
    if assistant_message is not None:
        assistant_message.ui_parts = ui_parts
        assistant_message.content_blocks = content_blocks
        assistant_message.trace_summary = trace_summary
        assistant_message.final_text = final_text or None
        assistant_message.raw_blocks = None
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
