from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

from .models import ExecRequest, ExecResult
from .validation import validate_workspace_filename

_DEFAULT_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
_RESERVED_WORKSPACE_FILES = {"main.py"}


def _safe_relative_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise ValueError(f"workspace file path must be relative: {raw_path!r}")
    if not path.parts:
        raise ValueError("workspace file path cannot be empty")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"workspace file path may not escape the workspace: {raw_path!r}")
    validate_workspace_filename(path.as_posix())
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


def _build_env(
    workspace: Path,
    user_env: dict[str, str],
    *,
    extra_env: dict[str, str] | None = None,
    python_executable: str | None = None,
) -> dict[str, str]:
    env = {
        "HOME": str(workspace),
        "PATH": os.getenv("PATH", _DEFAULT_PATH),
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_INPUT": "1",
        "TMPDIR": str(workspace),
        "XDG_CACHE_HOME": str(workspace / ".cache"),
        "LANG": "C.UTF-8",
        "PYTHONNOUSERSITE": "1",
    }
    if python_executable:
        python_path = Path(python_executable)
        env["VIRTUAL_ENV"] = str(python_path.parent.parent)
        env["PATH"] = os.pathsep.join([str(python_path.parent), env["PATH"]])
    if extra_env:
        for key, value in extra_env.items():
            env[key] = value
    for key, value in user_env.items():
        from .validation import validate_env_name

        validate_env_name(key)
        env[key] = value
    env["PIP_CACHE_DIR"] = env.get("PIP_CACHE_DIR", str(workspace / ".cache" / "pip"))
    Path(env["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)
    Path(env["PIP_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)
    return env


def execute_python_in_workspace(
    request: ExecRequest,
    *,
    workspace: Path,
    python_executable: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> ExecResult:
    started = perf_counter()
    workspace.mkdir(parents=True, exist_ok=True)
    _write_workspace_files(workspace, request.files)
    script_path = workspace / "main.py"
    script_path.write_text(request.code, encoding="utf-8")

    before = _snapshot_files(workspace)
    env = _build_env(
        workspace,
        request.env,
        extra_env=extra_env,
        python_executable=python_executable,
    )
    executable = python_executable or sys.executable

    try:
        completed = subprocess.run(
            [executable, "-I", str(script_path)],
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


def execute_python(request: ExecRequest) -> ExecResult:
    with tempfile.TemporaryDirectory(prefix="cloud-sandbox-") as workspace_name:
        workspace = Path(workspace_name)
        return execute_python_in_workspace(request, workspace=workspace, python_executable=sys.executable)
