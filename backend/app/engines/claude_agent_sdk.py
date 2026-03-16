from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterable

from app.core.config import get_settings


class ClaudeAgentSdkAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def launch(
        self,
        run_id: str,
        skill_id: str,
        prompt: str,
        conversation_title: str,
        skill_prompt: str,
        conversation_context: str,
    ) -> subprocess.Popen:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.settings.backend_root)
        if self.settings.agent_mode not in {"claude-agent-sdk", "claude-code"}:
            raise RuntimeError(f"Unsupported CLAUDE_AGENT_MODE: {self.settings.agent_mode}")
        env["AGENT_SKILL_PROMPT"] = skill_prompt
        env["AGENT_CONVERSATION_CONTEXT"] = conversation_context
        env["CLAUDE_AGENT_USE_FIXTURE_DATA"] = "true" if self.settings.claude_agent_use_fixture_data else "false"
        env["CLAUDE_AGENT_FIXTURE_DELAY_MS"] = str(self.settings.claude_agent_fixture_delay_ms)
        command = [
            self.settings.python_executable,
            "-m",
            "app.runtime.claude_agent_sdk_process",
            "--run-id",
            run_id,
            "--skill-id",
            skill_id,
            "--conversation-title",
            conversation_title,
            "--prompt",
            prompt,
        ]
        return subprocess.Popen(
            command,
            cwd=str(self.settings.repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def iter_raw_events(self, process: subprocess.Popen) -> Iterable[dict]:
        assert process.stdout is not None
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)
        return_code = process.wait()
        if return_code != 0:
            stderr = process.stderr.read() if process.stderr else ""
            raise RuntimeError(stderr or f"claude agent runtime exited with {return_code}")

    def cancel(self, process: subprocess.Popen) -> None:
        if process.poll() is None:
            process.terminate()

    def map_event(self, raw_event: dict) -> list[dict]:
        return [raw_event]
