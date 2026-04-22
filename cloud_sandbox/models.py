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


def result_to_dict(result: ExecResult) -> dict[str, Any]:
    return asdict(result)

