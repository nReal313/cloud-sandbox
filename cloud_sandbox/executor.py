from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

from .models import ExecRequest, ExecResult

_DEFAULT_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


def _safe_relative_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise ValueError(f"workspace file path must be relative: {raw_path!r}")
    if not path.parts:
        raise ValueError("workspace file path cannot be empty")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"workspace file path may not escape the workspace: {raw_path!r}")
    return path


def _write_workspace_files(workspace: Path, files: dict[str, str]) -> list[str]:
    written: list[str] = []
    for raw_path, content in files.items():
        relative_path = _safe_relative_path(raw_path)
        target = workspace / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(relative_path.as_posix())
    return written


def _snapshot_files(workspace: Path) -> set[str]:
    snapshot: set[str] = set()
    for path in workspace.rglob("*"):
        if path.is_file():
            snapshot.add(path.relative_to(workspace).as_posix())
    return snapshot


def _build_env(workspace: Path, user_env: dict[str, str]) -> dict[str, str]:
    env = {
        "HOME": str(workspace),
        "PATH": os.getenv("PATH", _DEFAULT_PATH),
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(workspace),
        "LANG": "C.UTF-8",
    }
    for key, value in user_env.items():
        if not key or not key.replace("_", "").isalnum() or not key[0].isalpha():
            raise ValueError(f"invalid environment variable name: {key!r}")
        env[key] = value
    return env


def execute_python(request: ExecRequest) -> ExecResult:
    started = perf_counter()
    with tempfile.TemporaryDirectory(prefix="cloud-sandbox-") as workspace_name:
        workspace = Path(workspace_name)
        _write_workspace_files(workspace, request.files)
        script_path = workspace / "main.py"
        script_path.write_text(request.code, encoding="utf-8")

        before = _snapshot_files(workspace)
        env = _build_env(workspace, request.env)

        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(script_path)],
                input=(request.stdin or "").encode("utf-8"),
                cwd=workspace,
                env=env,
                capture_output=True,
                check=False,
                timeout=request.timeout_seconds,
            )
            exit_code = completed.returncode
            stdout = completed.stdout.decode("utf-8", errors="replace")
            stderr = completed.stderr.decode("utf-8", errors="replace")
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = (exc.stdout or b"").decode("utf-8", errors="replace")
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
            stderr = f"{stderr}\n[timeout after {request.timeout_seconds:g}s]".strip()
            timed_out = True

        after = _snapshot_files(workspace)
        artifact_paths = sorted(after - before)
        duration_ms = int((perf_counter() - started) * 1000)
        return ExecResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
            artifact_paths=artifact_paths,
        )
