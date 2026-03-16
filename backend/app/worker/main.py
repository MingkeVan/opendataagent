from __future__ import annotations

import argparse
import time

from app.core.config import get_settings
from app.db.init_schema import init_schema
from app.db.session import session_scope
from app.engines.claude_agent_sdk import ClaudeAgentSdkAdapter
from app.services.conversation_service import get_conversation
from app.services.run_service import (
    build_conversation_context,
    claim_next_run,
    complete_run,
    fail_run,
    get_last_user_prompt,
    get_latest_seq,
    get_run,
    get_skill_snapshot,
    process_agent_event,
    update_run_context,
)


def _process_run(run_id: str) -> None:
    adapter = ClaudeAgentSdkAdapter()

    with session_scope() as session:
        run = get_run(session, run_id)
        if run is None:
            return
        conversation = get_conversation(session, run.conversation_id)
        snapshot = get_skill_snapshot(session, run.skill_snapshot_id)
        prompt = get_last_user_prompt(session, run.conversation_id)
        conversation_context = build_conversation_context(session, run.conversation_id, run.id)
        conversation_title = conversation.title if conversation is not None else "对话"
        update_run_context(
            run,
            {
                "currentPrompt": prompt,
                "conversationContext": conversation_context,
                "conversationTitle": conversation_title,
                "skillPrompt": snapshot.prompt_text,
            },
        )
        seq = get_latest_seq(session, run.id)

    process = adapter.launch(
        run_id=run_id,
        skill_id=snapshot.skill_id,
        prompt=prompt,
        conversation_title=conversation_title,
        skill_prompt=snapshot.prompt_text,
        conversation_context=conversation_context,
    )

    try:
        for raw_event in adapter.iter_raw_events(process):
            with session_scope() as session:
                run = get_run(session, run_id)
                if run is None:
                    adapter.cancel(process)
                    return
                if run.cancel_requested:
                    adapter.cancel(process)
                    fail_run(session, run, "cancelled", "cancelled", "Run cancelled by user")
                    return
                seq = process_agent_event(session, run, seq, raw_event)
                if raw_event["type"] == "finish":
                    complete_run(session, run, "completed")
                    return
    except Exception as exc:
        with session_scope() as session:
            run = get_run(session, run_id)
            if run is not None:
                fail_run(session, run, "failed", "worker_error", str(exc))
        raise


def process_next_run() -> str | None:
    with session_scope() as session:
        run = claim_next_run(session)
    if run is None:
        return None
    _process_run(run.id)
    return run.id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    init_schema()
    poll_interval = get_settings().worker_poll_interval_ms / 1000
    while True:
        run_id = process_next_run()
        if args.once:
            break
        if run_id is None:
            time.sleep(poll_interval)


if __name__ == "__main__":
    main()
