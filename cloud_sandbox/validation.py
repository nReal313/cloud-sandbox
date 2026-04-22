from __future__ import annotations

import math
import re

DEFAULT_SESSION_TTL_SECONDS = 3600.0
MAX_SESSION_TTL_SECONDS = 24 * 60 * 60

GCP_PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
BIGQUERY_DATASET_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,1023}$")
GCS_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
FIRESTORE_COLLECTION_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")

_PACKAGE_REQUIREMENT_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*"
    r"(?:\[[A-Za-z0-9_.,-]+\])?"
    r"(?:\s*(?:===|==|!=|<=|>=|~=)\s*[A-Za-z0-9*+!_.-]+)?$"
)

_PROTECTED_ENV_KEYS = {
    "HOME",
    "LANG",
    "PATH",
    "PIP_CACHE_DIR",
    "PIP_CONFIG_FILE",
    "PIP_DISABLE_PIP_VERSION_CHECK",
    "PIP_NO_INPUT",
    "PIP_REQUIRE_VIRTUALENV",
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONNOUSERSITE",
    "PYTHONUNBUFFERED",
    "PYTHONDONTWRITEBYTECODE",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "TMPDIR",
    "VIRTUAL_ENV",
    "XDG_CACHE_HOME",
}

_RESERVED_WORKSPACE_FILES = {"main.py", "_cloud_sandbox_runtime.py"}


def normalize_session_ttl(ttl_seconds: float | int | None) -> float:
    ttl = DEFAULT_SESSION_TTL_SECONDS if ttl_seconds is None else float(ttl_seconds)
    if not math.isfinite(ttl):
        raise ValueError("ttl_seconds must be a finite number")
    if ttl <= 0:
        raise ValueError("ttl_seconds must be greater than zero")
    if ttl > MAX_SESSION_TTL_SECONDS:
        raise ValueError(
            f"ttl_seconds must not exceed {MAX_SESSION_TTL_SECONDS} seconds"
        )
    return ttl


def validate_requirement(requirement: str) -> str:
    normalized = requirement.strip()
    if not normalized:
        raise ValueError("package requirement cannot be empty")
    if normalized.startswith("-"):
        raise ValueError(f"package requirement may not start with '-': {requirement!r}")
    if any(ch.isspace() for ch in normalized):
        raise ValueError(f"package requirement may not contain whitespace: {requirement!r}")
    if any(ch in normalized for ch in {"\\", "/", "\x00"}):
        raise ValueError(f"package requirement contains an unsafe path character: {requirement!r}")
    if not _PACKAGE_REQUIREMENT_RE.fullmatch(normalized):
        raise ValueError(f"invalid package requirement: {requirement!r}")
    return normalized


def validate_requirements(requirements: list[str]) -> list[str]:
    if not requirements:
        raise ValueError("packages cannot be empty")
    return [validate_requirement(requirement) for requirement in requirements]


def validate_env_name(name: str) -> str:
    if not name or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"invalid environment variable name: {name!r}")
    if name in _PROTECTED_ENV_KEYS:
        raise ValueError(f"environment variable may not override sandbox reserved key: {name!r}")
    return name


def validate_workspace_filename(path: str) -> str:
    if path in _RESERVED_WORKSPACE_FILES:
        raise ValueError(f"workspace file path is reserved: {path!r}")
    return path


def validate_gcp_project_id(project_id: str) -> str:
    normalized = project_id.strip()
    if not normalized:
        raise ValueError("gcp project_id cannot be empty")
    if not GCP_PROJECT_ID_RE.fullmatch(normalized):
        raise ValueError(f"invalid gcp project_id: {project_id!r}")
    return normalized


def validate_bigquery_dataset_id(dataset_id: str) -> str:
    normalized = dataset_id.strip()
    if not normalized:
        raise ValueError("bigquery dataset id cannot be empty")
    if not BIGQUERY_DATASET_ID_RE.fullmatch(normalized):
        raise ValueError(f"invalid bigquery dataset id: {dataset_id!r}")
    return normalized


def validate_gcs_bucket_name(bucket_name: str) -> str:
    normalized = bucket_name.strip()
    if not normalized:
        raise ValueError("gcs bucket name cannot be empty")
    if not GCS_BUCKET_NAME_RE.fullmatch(normalized):
        raise ValueError(f"invalid gcs bucket name: {bucket_name!r}")
    return normalized


def validate_firestore_collection_name(collection_name: str) -> str:
    normalized = collection_name.strip()
    if not normalized:
        raise ValueError("firestore collection name cannot be empty")
    if "/" in normalized:
        raise ValueError(f"firestore collection name may not contain '/': {collection_name!r}")
    if not FIRESTORE_COLLECTION_NAME_RE.fullmatch(normalized):
        raise ValueError(f"invalid firestore collection name: {collection_name!r}")
    return normalized
