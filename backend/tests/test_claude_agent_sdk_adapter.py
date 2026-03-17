from __future__ import annotations

import subprocess
import sys

import pytest

from app.core.config import reset_settings_cache
from app.engines.claude_agent_sdk import ClaudeAgentSdkAdapter
from app.runtime.claude_agent_sdk_process import has_valid_protocol_answer, replace_text_blocks


def test_iter_raw_events_yields_json_lines(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SDK_TIMEOUT_SECONDS", "5")
    reset_settings_cache()
    adapter = ClaudeAgentSdkAdapter()
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import json; "
                "print(json.dumps({'type': 'run-context'}), flush=True); "
                "print(json.dumps({'type': 'finish'}), flush=True)"
            ),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    events = list(adapter.iter_raw_events(process))

    assert [event["type"] for event in events] == ["run-context", "finish"]


def test_iter_raw_events_times_out_when_child_emits_nothing(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SDK_TIMEOUT_SECONDS", "1")
    reset_settings_cache()
    adapter = ClaudeAgentSdkAdapter()
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    with pytest.raises(RuntimeError, match="produced no output"):
        list(adapter.iter_raw_events(process))


def test_protocol_helpers_validate_and_replace_text_blocks() -> None:
    assert has_valid_protocol_answer(
        "<analysis_summary>业务对象：客户</analysis_summary>\n"
        "<final_answer>本月销售额最高的是木棉生活。</final_answer>"
    )
    assert not has_valid_protocol_answer(
        "<analysis_summary>业务对象：客户</analysis_summary>\n本月销售额最高的是木棉生活。"
    )

    blocks = [
        {"type": "tool_use", "id": "tool_1"},
        {"type": "text", "text": "旧文本 1"},
        {"type": "text", "text": "旧文本 2"},
    ]
    assert replace_text_blocks(blocks, "<final_answer>新文本</final_answer>") == [
        {"type": "tool_use", "id": "tool_1"},
        {"type": "text", "text": "<final_answer>新文本</final_answer>"},
    ]
