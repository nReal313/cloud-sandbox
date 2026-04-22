from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import uuid
import venv
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .connectors import (
    RUNTIME_MODULE_FILENAME,
    build_service_capabilities,
    build_session_capabilities,
    render_runtime_source,
)
from .executor import build_session_bootstrap_source, execute_python_in_workspace, _snapshot_files
from .models import ExecRequest, ExecResult, InstallResult, SessionConnectorConfig, SessionInfo
from .validation import normalize_session_ttl, validate_requirements

SESSION_STATUS_ACTIVE = "active"
SESSION_STATUS_DELETED = "deleted"
SESSION_STATUS_EXPIRED = "expired"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _ensure_workspace_dirs(root_dir: Path) -> tuple[Path, Path, Path, Path]:
    code_dir = root_dir / "workspace"
    tmp_dir = code_dir / "tmp"
    cache_dir = root_dir / "cache"
    pip_cache_dir = cache_dir / "pip"
    code_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    pip_cache_dir.mkdir(parents=True, exist_ok=True)
    return code_dir, tmp_dir, cache_dir, pip_cache_dir


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    status: str
    backend: str
    image: str
    runtime_class: str
    ttl_seconds: float
    connectors: SessionConnectorConfig | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    root_dir: Path
    code_dir: Path
    venv_dir: Path
    python_executable: Path
    installed_packages: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    last_exec_at: datetime | None = None
    last_exec_started_at: datetime | None = None
    last_exec_finished_at: datetime | None = None
    last_exec_exit_code: int | None = None
    last_error: str | None = None

    def to_info(self) -> SessionInfo:
        return SessionInfo(
            session_id=self.session_id,
            status=self.status,
            backend=self.backend,
            image=self.image,
            runtime_class=self.runtime_class,
            ttl_seconds=self.ttl_seconds,
            connectors=self.connectors,
            created_at=_to_iso(self.created_at) or "",
            updated_at=_to_iso(self.updated_at) or "",
            expires_at=_to_iso(self.expires_at) or "",
            workspace_dir=str(self.root_dir),
            code_dir=str(self.code_dir),
            venv_dir=str(self.venv_dir),
            python_executable=str(self.python_executable),
            installed_packages=list(self.installed_packages),
            artifact_paths=list(self.artifact_paths),
            last_exec_at=_to_iso(self.last_exec_at),
            last_exec_started_at=_to_iso(self.last_exec_started_at),
            last_exec_finished_at=_to_iso(self.last_exec_finished_at),
            last_exec_exit_code=self.last_exec_exit_code,
            last_error=self.last_error,
        )


class SessionManager:
    def __init__(
        self,
        *,
        root_dir: str | Path | None = None,
        default_ttl_seconds: float = 3600.0,
        backend_name: str = "local",
        default_image: str = "cloud-sandbox:latest",
        default_runtime_class: str = "gvisor",
    ) -> None:
        self._root_dir = Path(root_dir) if root_dir is not None else Path(tempfile.gettempdir()) / "cloud-sandbox"
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl_seconds = default_ttl_seconds
        self._backend_name = backend_name
        self._default_image = default_image
        self._default_runtime_class = default_runtime_class
        self._lock = threading.RLock()
        self._sessions: dict[str, SessionRecord] = {}
        self._session_locks: dict[str, threading.RLock] = {}
        self._idempotency_index: dict[str, str] = {}

    def create_session(
        self,
        *,
        ttl_seconds: float | int | None = None,
        image: str | None = None,
        runtime_class: str | None = None,
        connectors: SessionConnectorConfig | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[SessionInfo, bool]:
        ttl = normalize_session_ttl(ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds)
        with self._lock:
            self._purge_expired_locked()
            if idempotency_key:
                existing_session_id = self._idempotency_index.get(idempotency_key)
                if existing_session_id and existing_session_id in self._sessions:
                    return self._sessions[existing_session_id].to_info(), False

        session_id = uuid.uuid4().hex
        root_dir = self._root_dir / session_id
        code_dir, _, cache_dir, pip_cache_dir = _ensure_workspace_dirs(root_dir)
        venv_dir = root_dir / "venv"
        env_builder = venv.EnvBuilder(with_pip=True, clear=True, symlinks=os.name != "nt")
        env_builder.create(str(venv_dir))
        python_executable = _venv_python_path(venv_dir)
        if not python_executable.exists():
            raise RuntimeError(f"venv python executable not found at {python_executable}")

        runtime_module_path = code_dir / RUNTIME_MODULE_FILENAME
        runtime_module_path.write_text(render_runtime_source(connectors), encoding="utf-8")

        created_at = _utcnow()
        record = SessionRecord(
            session_id=session_id,
            status=SESSION_STATUS_ACTIVE,
            backend=self._backend_name,
            image=image or self._default_image,
            runtime_class=runtime_class or self._default_runtime_class,
            ttl_seconds=ttl,
            connectors=connectors,
            created_at=created_at,
            updated_at=created_at,
            expires_at=created_at + timedelta(seconds=ttl),
            root_dir=root_dir,
            code_dir=code_dir,
            venv_dir=venv_dir,
            python_executable=python_executable,
        )
        with self._lock:
            self._sessions[session_id] = record
            self._session_locks[session_id] = threading.RLock()
            if idempotency_key:
                self._idempotency_index[idempotency_key] = session_id
        return record.to_info(), True

    def get_session(self, session_id: str) -> SessionInfo:
        record = self._require_session_record(session_id)
        return record.to_info()

    def get_artifacts(self, session_id: str) -> list[str]:
        record = self._require_session_record(session_id)
        return list(record.artifact_paths)

    def get_capabilities(self, session_id: str) -> dict[str, object]:
        record = self._require_session_record(session_id)
        return build_session_capabilities(record.session_id, record.connectors)

    def get_service_capabilities(self) -> dict[str, object]:
        return build_service_capabilities()

    def delete_session(self, session_id: str) -> SessionInfo:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise KeyError(f"session not found: {session_id}")
            session_lock = self._session_locks.get(session_id)

        if session_lock is not None:
            with session_lock:
                with self._lock:
                    record = self._sessions.pop(session_id, record)
                    self._session_locks.pop(session_id, None)
                    self._drop_idempotency_mapping_locked(session_id)
            record.status = SESSION_STATUS_DELETED
            record.updated_at = _utcnow()
            shutil.rmtree(record.root_dir, ignore_errors=True)
            return record.to_info()

        with self._lock:
            record = self._sessions.pop(session_id)
            self._session_locks.pop(session_id, None)
            self._drop_idempotency_mapping_locked(session_id)
        record.status = SESSION_STATUS_DELETED
        record.updated_at = _utcnow()
        shutil.rmtree(record.root_dir, ignore_errors=True)
        return record.to_info()

    def install_packages(self, session_id: str, packages: list[str]) -> tuple[SessionInfo, InstallResult]:
        validated_packages = validate_requirements(packages)
        record = self._require_session_record(session_id)
        session_lock = self._require_session_lock(session_id)
        with session_lock:
            started = _utcnow()
            extra_env = self._build_session_env(record)
            command = [
                str(record.python_executable),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                *validated_packages,
            ]
            completed = self._run_subprocess(
                command,
                cwd=record.root_dir,
                extra_env=extra_env,
                timeout_seconds=300.0,
            )
            result = InstallResult(
                packages=list(validated_packages),
                stdout=completed.stdout,
                stderr=completed.stderr,
                exit_code=completed.exit_code,
                duration_ms=completed.duration_ms,
            )
            if result.exit_code == 0:
                installed = list(record.installed_packages)
                for package in validated_packages:
                    if package not in installed:
                        installed.append(package)
                record.installed_packages = installed
                record.last_error = None
            else:
                record.last_error = result.stderr or f"pip install failed with exit code {result.exit_code}"
            record.updated_at = _utcnow()
            return record.to_info(), result

    def exec_code(self, session_id: str, request: ExecRequest) -> tuple[SessionInfo, ExecResult]:
        record = self._require_session_record(session_id)
        session_lock = self._require_session_lock(session_id)
        with session_lock:
            if record.status != SESSION_STATUS_ACTIVE:
                raise KeyError(f"session is not active: {session_id}")
            started = _utcnow()
            before = set(_snapshot_files(record.code_dir))
            extra_env = self._build_session_env(record)
            result = execute_python_in_workspace(
                request,
                workspace=record.code_dir,
                python_executable=str(record.python_executable),
                extra_env=extra_env,
                script_source=build_session_bootstrap_source(request.code),
            )
            after = set(_snapshot_files(record.code_dir))
            new_artifacts = sorted(after - before)
            combined_artifacts = list(record.artifact_paths)
            for artifact in new_artifacts:
                if artifact not in combined_artifacts:
                    combined_artifacts.append(artifact)
            record.artifact_paths = sorted(combined_artifacts)
            now = _utcnow()
            record.last_exec_at = now
            record.last_exec_started_at = started
            record.last_exec_finished_at = now
            record.last_exec_exit_code = result.exit_code
            record.last_error = result.stderr if result.exit_code != 0 or result.timed_out else None
            record.updated_at = now
            result.session_id = session_id
            return record.to_info(), result

    def cleanup_expired(self) -> None:
        with self._lock:
            self._purge_expired_locked()

    def close(self) -> None:
        with self._lock:
            session_ids = list(self._sessions)
            self._sessions.clear()
            self._session_locks.clear()
            self._idempotency_index.clear()
        for session_id in session_ids:
            shutil.rmtree(self._root_dir / session_id, ignore_errors=True)

    def _build_session_env(self, record: SessionRecord) -> dict[str, str]:
        venv_bin_dir = record.python_executable.parent
        env = {
            "HOME": str(record.code_dir),
            "LANG": "C.UTF-8",
            "PATH": os.pathsep.join([str(venv_bin_dir), os.getenv("PATH", "")]),
            "TMPDIR": str(record.code_dir / "tmp"),
            "XDG_CACHE_HOME": str(record.root_dir / "cache"),
            "PIP_CACHE_DIR": str(record.root_dir / "cache" / "pip"),
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INPUT": "1",
            "PIP_REQUIRE_VIRTUALENV": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "VIRTUAL_ENV": str(record.venv_dir),
        }
        gcp_config = record.connectors.gcp if record.connectors and record.connectors.gcp else None
        if gcp_config is not None:
            env["GOOGLE_CLOUD_PROJECT"] = gcp_config.project_id
            env["GCLOUD_PROJECT"] = gcp_config.project_id
        return env

    def _require_session_record(self, session_id: str) -> SessionRecord:
        self.cleanup_expired()
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise KeyError(f"session not found: {session_id}")
            return record

    def _require_session_lock(self, session_id: str) -> threading.RLock:
        with self._lock:
            session_lock = self._session_locks.get(session_id)
            if session_lock is None:
                raise KeyError(f"session lock not found: {session_id}")
            return session_lock

    def _purge_expired_locked(self) -> None:
        now = _utcnow()
        expired_ids = [session_id for session_id, record in self._sessions.items() if record.expires_at <= now]
        for session_id in expired_ids:
            record = self._sessions.pop(session_id, None)
            self._session_locks.pop(session_id, None)
            self._drop_idempotency_mapping_locked(session_id)
            if record is not None:
                record.status = SESSION_STATUS_EXPIRED
                record.updated_at = now
                shutil.rmtree(record.root_dir, ignore_errors=True)

    def _drop_idempotency_mapping_locked(self, session_id: str) -> None:
        for key, existing_session_id in list(self._idempotency_index.items()):
            if existing_session_id == session_id:
                self._idempotency_index.pop(key, None)

    def _run_subprocess(
        self,
        command: list[str],
        *,
        cwd: Path,
        extra_env: dict[str, str],
        timeout_seconds: float,
    ) -> InstallResult:
        started = _utcnow()
        env = os.environ.copy()
        env.update(extra_env)
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                capture_output=True,
                check=False,
                text=True,
                timeout=timeout_seconds,
            )
            duration_ms = int((_utcnow() - started).total_seconds() * 1000)
            return InstallResult(
                packages=[],
                stdout=completed.stdout,
                stderr=completed.stderr,
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((_utcnow() - started).total_seconds() * 1000)
            stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
            stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
            stderr = f"{stderr}\n[timeout after {timeout_seconds:g}s]".strip()
            return InstallResult(
                packages=[],
                stdout=stdout,
                stderr=stderr,
                exit_code=124,
                duration_ms=duration_ms,
            )
