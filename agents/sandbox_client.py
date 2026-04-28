from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class CloudSandboxHTTPError(RuntimeError):
    def __init__(self, status: int, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(f"cloud sandbox request failed with HTTP {status}: {message}")
        self.status = status
        self.payload = payload or {}


@dataclass(slots=True)
class CloudSandboxClient:
    base_url: str
    default_timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def create_session(
        self,
        *,
        idempotency_key: str | None = None,
        ttl_seconds: float | int | None = None,
        connectors: dict[str, Any] | None = None,
        image: str | None = None,
        runtime_class: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if ttl_seconds is not None:
            payload["ttl_seconds"] = ttl_seconds
        if connectors is not None:
            payload["connectors"] = connectors
        if image is not None:
            payload["image"] = image
        if runtime_class is not None:
            payload["runtime_class"] = runtime_class

        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return self._request("POST", "/sessions", payload=payload, headers=headers)

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}")

    def delete_session(self, session_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/sessions/{session_id}")

    def get_capabilities(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}/capabilities")

    def list_artifacts(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}/artifacts")

    def install_packages(self, session_id: str, packages: list[str]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/sessions/{session_id}/install",
            payload={"packages": packages},
        )

    def exec_python(
        self,
        session_id: str,
        code: str,
        *,
        timeout_seconds: float | int | None = None,
        stdin: str = "",
        env: dict[str, str] | None = None,
        files: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/sessions/{session_id}/exec",
            payload={
                "code": code,
                "timeout_seconds": timeout_seconds or self.default_timeout_seconds,
                "stdin": stdin,
                "env": env or {},
                "files": files or {},
            },
        )

    def exec_shell(
        self,
        session_id: str,
        command: str,
        *,
        timeout_seconds: float | int | None = None,
        stdin: str = "",
        env: dict[str, str] | None = None,
        files: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/sessions/{session_id}/shell",
            payload={
                "command": command,
                "timeout_seconds": timeout_seconds or self.default_timeout_seconds,
                "stdin": stdin,
                "env": env or {},
                "files": files or {},
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request_headers = {"Accept": "application/json"}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        if headers:
            request_headers.update(headers)

        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.default_timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                error_payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                error_payload = {"error": raw}
            message = str(error_payload.get("error") or raw or exc.reason)
            raise CloudSandboxHTTPError(exc.code, message, error_payload) from exc
