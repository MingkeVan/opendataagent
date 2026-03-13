from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterable

from app.core.config import get_settings


class ClaudeAgentSdkAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def launch(self, run_id: str, skill_id: str, prompt: str, conversation_title: str) -> subprocess.Popen:
        if self.settings.agent_mode != "mock":
            raise RuntimeError("Only mock mode is implemented for local MVP execution.")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.settings.backend_root)
        env["MOCK_AGENT_DELAY_MS"] = str(self.settings.mock_agent_delay_ms)
        command = [
            "python3",
            "-m",
            "app.runtime.mock_agent_process",
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
            raise RuntimeError(stderr or f"mock agent exited with {return_code}")

    def cancel(self, process: subprocess.Popen) -> None:
        if process.poll() is None:
            process.terminate()

    def map_event(self, raw_event: dict) -> list[dict]:
        return [raw_event]

