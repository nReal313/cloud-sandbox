from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ExecRequest:
    code: str
    timeout_seconds: float = 10.0
    stdin: str = ""
    env: dict[str, str] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    artifact_paths: list[str] = field(default_factory=list)
    session_id: str | None = None


@dataclass(slots=True)
class GcpConnectorConfig:
    project_id: str
    bigquery_default_dataset: str | None = None
    gcs_bucket: str | None = None
    firestore_collection: str | None = None


@dataclass(slots=True)
class SessionConnectorConfig:
    gcp: GcpConnectorConfig | None = None


@dataclass(slots=True)
class InstallRequest:
    packages: list[str]


@dataclass(slots=True)
class InstallResult:
    packages: list[str]
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


@dataclass(slots=True)
class SessionInfo:
    session_id: str
    status: str
    backend: str
    image: str
    runtime_class: str
    ttl_seconds: float
    connectors: SessionConnectorConfig | None
    created_at: str
    updated_at: str
    expires_at: str
    workspace_dir: str
    code_dir: str
    venv_dir: str
    python_executable: str
    installed_packages: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    last_exec_at: str | None = None
    last_exec_started_at: str | None = None
    last_exec_finished_at: str | None = None
    last_exec_exit_code: int | None = None
    last_error: str | None = None


@dataclass(slots=True)
class SessionCreateRequest:
    ttl_seconds: float | None = None
    image: str | None = None
    runtime_class: str | None = None
    connectors: SessionConnectorConfig | None = None


def result_to_dict(result: ExecResult) -> dict[str, Any]:
    return asdict(result)


def session_to_dict(session: SessionInfo) -> dict[str, Any]:
    return asdict(session)


def install_result_to_dict(result: InstallResult) -> dict[str, Any]:
    return asdict(result)
