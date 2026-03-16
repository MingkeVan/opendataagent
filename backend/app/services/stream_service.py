from __future__ import annotations

import asyncio
import json

from app.core.config import get_settings
from app.db.session import session_scope
from app.services.run_service import (
    TERMINAL_RUN_STATUSES,
    build_stream_snapshot,
    get_assistant_message_for_run,
    get_run,
    list_run_events,
)


def encode_sse(payload: str, event_id: int | None = None) -> bytes:
    prefix = f"id: {event_id}\n" if event_id is not None else ""
    return f"{prefix}data: {payload}\n\n".encode("utf-8")


async def iter_run_stream(run_id: str, after_seq: int):
    last_seq = after_seq
    poll_interval = get_settings().stream_poll_interval_ms / 1000
    snapshot_sent = False

    while True:
        with session_scope() as session:
            run = get_run(session, run_id)
            if run is None:
                events = []
                snapshot = None
                assistant_message = None
            else:
                events = list_run_events(session, run_id, last_seq)
                snapshot = build_stream_snapshot(session, run) if not snapshot_sent and after_seq <= 0 else None
                assistant_message = get_assistant_message_for_run(session, run_id)

        if snapshot is not None:
            yield encode_sse(
                json.dumps(
                    {
                        "version": "v2",
                        "kind": "snapshot",
                        "runId": run_id,
                        "messageId": assistant_message.id if assistant_message is not None else None,
                        "seq": snapshot["latestSeq"],
                        "stepIndex": None,
                        "partId": "snapshot",
                        "payload": {
                            "uiParts": snapshot["uiParts"],
                            "traceSummary": snapshot["traceSummary"],
                            "finalText": snapshot["finalText"],
                        },
                    },
                    ensure_ascii=False,
                ),
                event_id=snapshot["latestSeq"] or 0,
            )
            snapshot_sent = True

        for event in events:
            last_seq = event.seq
            yield encode_sse(json.dumps(event.payload_json, ensure_ascii=False), event_id=event.seq)

        if run is None:
            yield encode_sse(
                json.dumps(
                    {
                        "version": "v2",
                        "kind": "status",
                        "runId": run_id,
                        "messageId": None,
                        "seq": last_seq,
                        "stepIndex": None,
                        "partId": "status",
                        "payload": {"runStatus": "failed", "reason": "run-not-found"},
                    },
                    ensure_ascii=False,
                ),
                event_id=last_seq or 0,
            )
            yield encode_sse(
                json.dumps(
                    {
                        "version": "v2",
                        "kind": "done",
                        "runId": run_id,
                        "messageId": None,
                        "seq": last_seq,
                        "stepIndex": None,
                        "partId": "done",
                        "payload": {"runStatus": "failed", "reason": "run-not-found"},
                    },
                    ensure_ascii=False,
                ),
                event_id=last_seq or 0,
            )
            yield encode_sse("[DONE]")
            break

        if run.status in TERMINAL_RUN_STATUSES and not events:
            yield encode_sse(
                json.dumps(
                    {
                        "version": "v2",
                        "kind": "status",
                        "runId": run.id,
                        "messageId": assistant_message.id if assistant_message is not None else None,
                        "seq": last_seq,
                        "stepIndex": None,
                        "partId": "status",
                        "payload": {
                            "runStatus": run.status,
                            "stopReason": run.stop_reason,
                            "usage": assistant_message.usage_json if assistant_message is not None else None,
                        },
                    },
                    ensure_ascii=False,
                ),
                event_id=last_seq or 0,
            )
            artifact_refs = []
            if assistant_message is not None:
                for part in assistant_message.ui_parts or []:
                    if part.get("type") == "data-artifact" and part.get("artifactId"):
                        artifact_refs.append(part["artifactId"])
            yield encode_sse(
                json.dumps(
                    {
                        "version": "v2",
                        "kind": "done",
                        "runId": run.id,
                        "messageId": assistant_message.id if assistant_message is not None else None,
                        "seq": last_seq,
                        "stepIndex": None,
                        "partId": "done",
                        "payload": {
                            "runStatus": run.status,
                            "stopReason": run.stop_reason,
                            "artifactRefs": artifact_refs,
                        },
                    },
                    ensure_ascii=False,
                ),
                event_id=last_seq or 0,
            )
            yield encode_sse("[DONE]")
            break

        await asyncio.sleep(poll_interval)
