from __future__ import annotations

from typing import Any

from .sandbox_backend import CloudSandboxBackend


def make_run_injected_python_tool(backend: CloudSandboxBackend):
    from langchain_core.tools import tool

    @tool
    def run_injected_python(code: str, timeout_seconds: int = 300) -> dict[str, Any]:
        """Run Python code in the cloud sandbox with sandbox globals injected.

        Use this for Python that needs `sandbox`, `sandbox_capabilities`,
        BigQuery, Firestore, GCS, or other cloud-sandbox runtime helpers.
        The code runs in the same session workspace as shell/file operations.
        """

        response = backend.client.exec_python(
            backend.session_id,
            code,
            timeout_seconds=timeout_seconds,
        )
        result = response["result"]
        return {
            "session_id": backend.session_id,
            "exit_code": result.get("exit_code"),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "timed_out": result.get("timed_out", False),
            "artifact_paths": result.get("artifact_paths", []),
        }

    return run_injected_python
