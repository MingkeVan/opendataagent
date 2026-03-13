from __future__ import annotations

import asyncio
import json

from app.core.config import get_settings
from app.db.session import session_scope
from app.services.run_service import TERMINAL_RUN_STATUSES, get_run, list_run_events


def encode_sse(payload: str) -> bytes:
    return f"data: {payload}\n\n".encode("utf-8")


async def iter_run_stream(run_id: str, after_seq: int):
    last_seq = after_seq
    poll_interval = get_settings().stream_poll_interval_ms / 1000

    while True:
        with session_scope() as session:
            events = list_run_events(session, run_id, last_seq)
            run = get_run(session, run_id)

        for event in events:
            last_seq = event.seq
            yield encode_sse(json.dumps({"seq": event.seq, **event.payload_json}, ensure_ascii=False))

        if run is None:
            yield encode_sse(json.dumps({"type": "abort", "reason": "run-not-found"}, ensure_ascii=False))
            yield encode_sse("[DONE]")
            break

        if run.status in TERMINAL_RUN_STATUSES and not events:
            yield encode_sse("[DONE]")
            break

        await asyncio.sleep(poll_interval)

