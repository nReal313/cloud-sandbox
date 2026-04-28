from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .sandbox_client import CloudSandboxClient

try:
    from deepagents.backends.sandbox import BaseSandbox, ExecuteResponse
except ImportError:  # pragma: no cover - exercised only when optional dependency is absent
    BaseSandbox = object  # type: ignore[assignment,misc]
    ExecuteResponse = None  # type: ignore[assignment]


@dataclass(slots=True)
class CloudSandboxBackendConfig:
    sandbox_url: str
    thread_id: str
    ttl_seconds: float | int = 3600
    connectors: dict[str, Any] | None = None
    image: str | None = None
    runtime_class: str | None = None
    default_timeout_seconds: float = 60.0


class CloudSandboxBackend(BaseSandbox):  # type: ignore[misc]
    """Deep Agents sandbox backend backed by this repo's cloud-sandbox service.

    The Deep Agents conversation/thread id is used as the sandbox service's
    Idempotency-Key, so repeated construction for the same thread resolves to
    the same sandbox session until that session expires.
    """

    def __init__(
        self,
        config: CloudSandboxBackendConfig,
        *,
        client: CloudSandboxClient | None = None,
    ) -> None:
        if ExecuteResponse is None:
            raise RuntimeError("deepagents is required to use CloudSandboxBackend")

        self.config = config
        self.client = client or CloudSandboxClient(
            config.sandbox_url,
            default_timeout_seconds=config.default_timeout_seconds,
        )
        response = self.client.create_session(
            idempotency_key=config.thread_id,
            ttl_seconds=config.ttl_seconds,
            connectors=config.connectors,
            image=config.image,
            runtime_class=config.runtime_class,
        )
        session = response["session"]
        self.session_id = session["session_id"]
        self.created = bool(response.get("created"))

    @property
    def id(self) -> str:
        return self.session_id

    @classmethod
    def for_thread(
        cls,
        *,
        sandbox_url: str,
        thread_id: str,
        ttl_seconds: float | int = 3600,
        connectors: dict[str, Any] | None = None,
        image: str | None = None,
        runtime_class: str | None = None,
        default_timeout_seconds: float = 60.0,
    ) -> "CloudSandboxBackend":
        return cls(
            CloudSandboxBackendConfig(
                sandbox_url=sandbox_url,
                thread_id=thread_id,
                ttl_seconds=ttl_seconds,
                connectors=connectors,
                image=image,
                runtime_class=runtime_class,
                default_timeout_seconds=default_timeout_seconds,
            )
        )

    def execute(self, command: str, *, timeout: int | None = None):  # type: ignore[no-untyped-def]
        timeout_seconds = timeout or int(self.config.default_timeout_seconds)
        result = self.client.exec_python(
            self.session_id,
            _shell_command_source(command, timeout_seconds),
            timeout_seconds=timeout_seconds + 5,
        )
        exec_result = result["result"]
        return _execute_response(
            stdout=exec_result.get("stdout", ""),
            stderr=exec_result.get("stderr", ""),
            exit_code=int(exec_result.get("exit_code", 1)),
            timed_out=bool(exec_result.get("timed_out", False)),
            artifact_paths=list(exec_result.get("artifact_paths", [])),
        )


def _shell_command_source(command: str, timeout_seconds: int) -> str:
    command_json = json.dumps(command)
    return (
        "from __future__ import annotations\n"
        "import subprocess\n"
        "import sys\n"
        f"command = {command_json}\n"
        "completed = subprocess.run(\n"
        "    command,\n"
        "    shell=True,\n"
        "    capture_output=True,\n"
        "    text=True,\n"
        f"    timeout={int(timeout_seconds)},\n"
        ")\n"
        "sys.stdout.write(completed.stdout)\n"
        "sys.stderr.write(completed.stderr)\n"
        "raise SystemExit(completed.returncode)\n"
    )


def _execute_response(
    *,
    stdout: str,
    stderr: str,
    exit_code: int,
    timed_out: bool,
    artifact_paths: list[str],
):  # type: ignore[no-untyped-def]
    combined_output = stdout
    if stderr:
        combined_output = f"{combined_output}{stderr}" if combined_output else stderr
    if timed_out:
        combined_output = f"{combined_output}\n[timeout]".strip()
    if artifact_paths:
        joined_artifacts = ", ".join(artifact_paths)
        combined_output = f"{combined_output}\n[artifacts: {joined_artifacts}]".strip()

    return ExecuteResponse(  # type: ignore[misc,operator]
        output=combined_output,
        exit_code=exit_code,
        truncated=False,
    )
