from __future__ import annotations

import json
import textwrap
from dataclasses import asdict
from typing import Any

from .models import GcpConnectorConfig, SessionConnectorConfig
from .validation import (
    validate_bigquery_dataset_id,
    validate_firestore_collection_name,
    validate_gcp_project_id,
    validate_gcs_bucket_name,
)

RUNTIME_MODULE_FILENAME = "_cloud_sandbox_runtime.py"

_BIGQUERY_METHODS = ["query_df", "query_rows", "read_table_df", "read_table_rows"]
_FIRESTORE_METHODS = ["write_metadata", "read_metadata", "delete_metadata"]
_GCS_METHODS = ["upload_bytes", "download_bytes", "upload_file", "download_file", "list_objects"]

_RUNTIME_TEMPLATE = textwrap.dedent(
    """
    from __future__ import annotations

    import json
    from pathlib import Path
    from typing import Any, Mapping

    _CONFIG = json.loads(__CONFIG_JSON__)


    def _missing_dependency(package_name: str) -> RuntimeError:
        return RuntimeError(f"{package_name} is required in this sandbox image")


    def _gcp_config() -> dict[str, Any] | None:
        gcp = _CONFIG.get("gcp")
        if not isinstance(gcp, dict):
            return None
        return gcp


    def _enabled_config() -> dict[str, Any]:
        gcp = _gcp_config()
        if gcp is None:
            raise RuntimeError("gcp connectors are not configured for this session")
        project_id = gcp.get("project_id")
        if not project_id:
            raise RuntimeError("gcp project_id is missing for this session")
        return gcp


    def _load_bigquery_module():
        try:
            from google.cloud import bigquery as bigquery_module
        except Exception as exc:  # pragma: no cover - runtime dependency path
            raise _missing_dependency("google-cloud-bigquery") from exc
        return bigquery_module


    def _load_firestore_module():
        try:
            from google.cloud import firestore as firestore_module
        except Exception as exc:  # pragma: no cover - runtime dependency path
            raise _missing_dependency("google-cloud-firestore") from exc
        return firestore_module


    def _load_storage_module():
        try:
            from google.cloud import storage as storage_module
        except Exception as exc:  # pragma: no cover - runtime dependency path
            raise _missing_dependency("google-cloud-storage") from exc
        return storage_module


    def _describe_gcp() -> dict[str, Any]:
        gcp = _gcp_config()
        enabled = gcp is not None and bool(gcp.get("project_id"))
        return {
            "enabled": enabled,
            "credential_source": "workload_identity",
            "project_id": gcp.get("project_id") if gcp else None,
            "bigquery_default_dataset": gcp.get("bigquery_default_dataset") if gcp else None,
            "gcs_bucket": gcp.get("gcs_bucket") if gcp else None,
            "firestore_collection": gcp.get("firestore_collection") if gcp else None,
            "bigquery": {
                "enabled": enabled,
                "methods": __BIGQUERY_METHODS__ if enabled else [],
            },
            "firestore": {
                "enabled": enabled,
                "methods": __FIRESTORE_METHODS__ if enabled else [],
            },
            "gcs": {
                "enabled": enabled,
                "methods": __GCS_METHODS__ if enabled else [],
            },
        }


    class BigQueryConnector:
        def __init__(self, config: dict[str, Any] | None) -> None:
            self._config = config or {}
            self._client = None

        def describe(self) -> dict[str, Any]:
            enabled = bool(self._config.get("project_id"))
            return {
                "enabled": enabled,
                "credential_source": "workload_identity",
                "project_id": self._config.get("project_id"),
                "default_dataset": self._config.get("bigquery_default_dataset"),
                "methods": __BIGQUERY_METHODS__ if enabled else [],
            }

        def _client_instance(self):
            if self._client is None:
                bigquery_module = _load_bigquery_module()
                self._client = bigquery_module.Client(project=self._config["project_id"])
            return self._client

        def query_rows(self, sql: str, *, job_config: Any | None = None) -> list[dict[str, Any]]:
            if not self._config.get("project_id"):
                raise RuntimeError("gcp bigquery connectors are not configured for this session")
            rows = self._client_instance().query(sql, job_config=job_config).result()
            return [dict(row.items()) for row in rows]

        def read_table_rows(self, table_ref: str) -> list[dict[str, Any]]:
            return self.query_rows(f"SELECT * FROM `{table_ref}`")

        def query_df(self, sql: str, *, job_config: Any | None = None):
            rows = self.query_rows(sql, job_config=job_config)
            try:
                import pandas as pd
            except Exception as exc:  # pragma: no cover - runtime dependency path
                raise _missing_dependency("pandas") from exc
            return pd.DataFrame(rows)

        def read_table_df(self, table_ref: str):
            return self.query_df(f"SELECT * FROM `{table_ref}`")


    class FirestoreConnector:
        def __init__(self, config: dict[str, Any] | None) -> None:
            self._config = config or {}
            self._client = None

        def describe(self) -> dict[str, Any]:
            enabled = bool(self._config.get("project_id"))
            return {
                "enabled": enabled,
                "credential_source": "workload_identity",
                "project_id": self._config.get("project_id"),
                "default_collection": self._config.get("firestore_collection"),
                "methods": __FIRESTORE_METHODS__ if enabled else [],
            }

        def _client_instance(self):
            if self._client is None:
                firestore_module = _load_firestore_module()
                self._client = firestore_module.Client(project=self._config["project_id"])
            return self._client

        def _document_ref(self, document_path: str):
            parts = [part for part in document_path.strip("/").split("/") if part]
            if not parts:
                raise ValueError("firestore document path cannot be empty")
            if len(parts) == 1:
                collection = self._config.get("firestore_collection")
                if not collection:
                    raise RuntimeError("firestore_collection is not configured for this session")
                parts = [collection, parts[0]]
            if len(parts) % 2 != 0:
                raise ValueError("firestore document path must contain collection/document pairs")
            return self._client_instance().document(*parts), "/".join(parts)

        def write_metadata(self, document_path: str, data: Mapping[str, Any], *, merge: bool = False) -> dict[str, Any]:
            document_ref, resolved_path = self._document_ref(document_path)
            document_ref.set(dict(data), merge=merge)
            return {"path": resolved_path, "merge": merge}

        def read_metadata(self, document_path: str) -> dict[str, Any] | None:
            document_ref, _ = self._document_ref(document_path)
            snapshot = document_ref.get()
            if not snapshot.exists:
                return None
            return snapshot.to_dict()

        def delete_metadata(self, document_path: str) -> dict[str, Any]:
            document_ref, resolved_path = self._document_ref(document_path)
            document_ref.delete()
            return {"path": resolved_path}


    class GcsConnector:
        def __init__(self, config: dict[str, Any] | None) -> None:
            self._config = config or {}
            self._client = None

        def describe(self) -> dict[str, Any]:
            enabled = bool(self._config.get("project_id"))
            return {
                "enabled": enabled,
                "credential_source": "workload_identity",
                "project_id": self._config.get("project_id"),
                "default_bucket": self._config.get("gcs_bucket"),
                "methods": __GCS_METHODS__ if enabled else [],
            }

        def _client_instance(self):
            if self._client is None:
                storage_module = _load_storage_module()
                self._client = storage_module.Client(project=self._config["project_id"])
            return self._client

        def _resolve_target(self, uri_or_path: str) -> tuple[Any, str, str]:
            if uri_or_path.startswith("gs://"):
                bucket_and_key = uri_or_path.removeprefix("gs://")
                bucket_name, _, object_name = bucket_and_key.partition("/")
                if not bucket_name or not object_name:
                    raise ValueError(f"invalid GCS URI: {uri_or_path!r}")
            else:
                bucket_name = self._config.get("gcs_bucket")
                if not bucket_name:
                    raise RuntimeError("gcs_bucket is not configured for this session")
                object_name = uri_or_path.lstrip("/")
                if not object_name:
                    raise ValueError("gcs object path cannot be empty")
            bucket = self._client_instance().bucket(bucket_name)
            return bucket.blob(object_name), bucket_name, object_name

        def upload_bytes(self, data: bytes | str, uri_or_path: str, *, content_type: str | None = None) -> dict[str, Any]:
            blob, bucket_name, object_name = self._resolve_target(uri_or_path)
            payload = data.encode("utf-8") if isinstance(data, str) else data
            blob.upload_from_string(payload, content_type=content_type)
            return {"uri": f"gs://{bucket_name}/{object_name}"}

        def download_bytes(self, uri_or_path: str) -> bytes:
            blob, _, _ = self._resolve_target(uri_or_path)
            return blob.download_as_bytes()

        def upload_file(self, local_path: str, uri_or_path: str, *, content_type: str | None = None) -> dict[str, Any]:
            blob, bucket_name, object_name = self._resolve_target(uri_or_path)
            blob.upload_from_filename(local_path, content_type=content_type)
            return {"uri": f"gs://{bucket_name}/{object_name}", "source_path": local_path}

        def download_file(self, uri_or_path: str, local_path: str) -> dict[str, Any]:
            blob, bucket_name, object_name = self._resolve_target(uri_or_path)
            blob.download_to_filename(local_path)
            return {"uri": f"gs://{bucket_name}/{object_name}", "destination_path": local_path}

        def list_objects(self, prefix: str = "") -> list[str]:
            bucket_name = self._config.get("gcs_bucket")
            if not bucket_name:
                raise RuntimeError("gcs_bucket is not configured for this session")
            bucket = self._client_instance().bucket(bucket_name)
            return [blob.name for blob in bucket.list_blobs(prefix=prefix or None)]


    class SandboxRuntime:
        def __init__(self, config: dict[str, Any] | None) -> None:
            self._config = config or {}
            gcp_config = self._config.get("gcp")
            if not isinstance(gcp_config, dict):
                gcp_config = None
            self.bigquery = BigQueryConnector(gcp_config)
            self.firestore = FirestoreConnector(gcp_config)
            self.gcs = GcsConnector(gcp_config)

        def capabilities(self) -> dict[str, Any]:
            return {
                "runtime": {
                    "injected_globals": ["sandbox", "sandbox_capabilities"],
                    "bootstrap_module": __RUNTIME_MODULE_FILENAME__,
                },
                "connectors": {
                    "gcp": _describe_gcp(),
                },
            }


    sandbox = SandboxRuntime(_CONFIG)
    """
)


def validate_session_gcp_connector_config(payload: Any) -> GcpConnectorConfig | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("connectors.gcp must be an object")

    project_id = payload.get("project_id")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("connectors.gcp.project_id must be a non-empty string")

    bigquery_default_dataset = payload.get("bigquery_default_dataset")
    if bigquery_default_dataset is not None:
        if not isinstance(bigquery_default_dataset, str) or not bigquery_default_dataset.strip():
            raise ValueError("connectors.gcp.bigquery_default_dataset must be a non-empty string")
        bigquery_default_dataset = validate_bigquery_dataset_id(bigquery_default_dataset)

    gcs_bucket = payload.get("gcs_bucket")
    if gcs_bucket is not None:
        if not isinstance(gcs_bucket, str) or not gcs_bucket.strip():
            raise ValueError("connectors.gcp.gcs_bucket must be a non-empty string")
        gcs_bucket = validate_gcs_bucket_name(gcs_bucket)

    firestore_collection = payload.get("firestore_collection")
    if firestore_collection is not None:
        if not isinstance(firestore_collection, str) or not firestore_collection.strip():
            raise ValueError("connectors.gcp.firestore_collection must be a non-empty string")
        firestore_collection = validate_firestore_collection_name(firestore_collection)

    return GcpConnectorConfig(
        project_id=validate_gcp_project_id(project_id),
        bigquery_default_dataset=bigquery_default_dataset,
        gcs_bucket=gcs_bucket,
        firestore_collection=firestore_collection,
    )


def parse_session_connectors(payload: Any) -> SessionConnectorConfig | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("connectors must be an object")
    if not payload:
        return None

    allowed_keys = {"gcp"}
    unknown_keys = set(payload) - allowed_keys
    if unknown_keys:
        keys = ", ".join(sorted(unknown_keys))
        raise ValueError(f"unsupported connector types: {keys}")

    gcp = validate_session_gcp_connector_config(payload.get("gcp"))
    if gcp is None:
        return None
    return SessionConnectorConfig(gcp=gcp)


def _connector_methods(enabled: bool, methods: list[str]) -> dict[str, Any]:
    return {"enabled": enabled, "methods": list(methods) if enabled else []}


def build_service_capabilities() -> dict[str, Any]:
    return {
        "service": "cloud-sandbox",
        "runtime": {
            "injected_globals": ["sandbox", "sandbox_capabilities"],
            "session_scoped": True,
        },
        "supported_connector_types": ["gcp"],
        "connector_configuration_fields": {
            "gcp": [
                "project_id",
                "bigquery_default_dataset",
                "gcs_bucket",
                "firestore_collection",
            ],
        },
        "connector_auth": {
            "gcp": "workload_identity",
        },
        "connector_methods": {
            "gcp": {
                "bigquery": _connector_methods(True, _BIGQUERY_METHODS),
                "firestore": _connector_methods(True, _FIRESTORE_METHODS),
                "gcs": _connector_methods(True, _GCS_METHODS),
            }
        },
        "endpoints": [
            "/capabilities",
            "/sessions/{id}/capabilities",
        ],
    }


def build_session_capabilities(session_id: str, connectors: SessionConnectorConfig | None) -> dict[str, Any]:
    gcp = connectors.gcp if connectors is not None else None
    enabled = gcp is not None
    return {
        "session_id": session_id,
        "runtime": {
            "injected_globals": ["sandbox", "sandbox_capabilities"],
            "bootstrap_module": RUNTIME_MODULE_FILENAME,
        },
        "connectors": {
            "gcp": {
                "enabled": enabled,
                "credential_source": "workload_identity",
                "project_id": gcp.project_id if gcp else None,
                "bigquery_default_dataset": gcp.bigquery_default_dataset if gcp else None,
                "gcs_bucket": gcp.gcs_bucket if gcp else None,
                "firestore_collection": gcp.firestore_collection if gcp else None,
                "bigquery": _connector_methods(enabled, _BIGQUERY_METHODS),
                "firestore": _connector_methods(enabled, _FIRESTORE_METHODS),
                "gcs": _connector_methods(enabled, _GCS_METHODS),
            }
        },
    }


def render_runtime_source(connectors: SessionConnectorConfig | None) -> str:
    runtime_config = {"gcp": asdict(connectors.gcp) if connectors and connectors.gcp else None}
    config_json = json.dumps(runtime_config, sort_keys=True, separators=(",", ":"))
    source = _RUNTIME_TEMPLATE.replace("__CONFIG_JSON__", repr(config_json))
    source = source.replace("__BIGQUERY_METHODS__", repr(_BIGQUERY_METHODS))
    source = source.replace("__FIRESTORE_METHODS__", repr(_FIRESTORE_METHODS))
    source = source.replace("__GCS_METHODS__", repr(_GCS_METHODS))
    source = source.replace("__RUNTIME_MODULE_FILENAME__", repr(RUNTIME_MODULE_FILENAME))
    return source
