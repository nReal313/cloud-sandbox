from __future__ import annotations

import json
import logging
import math
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

from .auth import AuthenticationError, require_bearer_auth
from .executor import execute_python
from .models import (
    ExecRequest,
    InstallRequest,
    SessionCreateRequest,
    install_result_to_dict,
    result_to_dict,
    session_to_dict,
)
from .sessions import SessionManager
from .validation import normalize_session_ttl, validate_requirements

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def _env_text(name: str, default: str | None = None) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value or default


def _normalize_path(path: str) -> str:
    normalized = urlparse(path).path or "/"
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    return normalized or "/"


def _split_session_path(path: str) -> tuple[str, str | None] | None:
    normalized = _normalize_path(path)
    if not normalized.startswith("/sessions"):
        return None

    parts = [part for part in normalized.strip("/").split("/") if part]
    if len(parts) == 1 and parts[0] == "sessions":
        return None
    if len(parts) == 2 and parts[0] == "sessions":
        return parts[1], None
    if len(parts) == 3 and parts[0] == "sessions":
        return parts[1], parts[2]
    return None


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    value = headers.get(name)
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def parse_exec_request(payload: Any) -> ExecRequest:
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")

    code = payload.get("code")
    if not isinstance(code, str) or not code.strip():
        raise ValueError("code must be a non-empty string")

    timeout_seconds = payload.get("timeout_seconds", 10.0)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise ValueError("timeout_seconds must be a number")
    timeout_seconds = float(timeout_seconds)
    if not math.isfinite(timeout_seconds):
        raise ValueError("timeout_seconds must be finite")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    stdin = payload.get("stdin", "")
    if stdin is None:
        stdin = ""
    if not isinstance(stdin, str):
        raise ValueError("stdin must be a string")

    env = payload.get("env", {})
    if not isinstance(env, dict):
        raise ValueError("env must be an object")
    cleaned_env: dict[str, str] = {}
    for key, value in env.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("env keys and values must be strings")
        cleaned_env[key] = value

    files = payload.get("files", {})
    if not isinstance(files, dict):
        raise ValueError("files must be an object")
    cleaned_files: dict[str, str] = {}
    for key, value in files.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("files keys and values must be strings")
        cleaned_files[key] = value

    return ExecRequest(
        code=code,
        timeout_seconds=timeout_seconds,
        stdin=stdin,
        env=cleaned_env,
        files=cleaned_files,
    )


def parse_session_create_request(payload: Any) -> SessionCreateRequest:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")

    ttl_seconds = payload.get("ttl_seconds")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float, type(None))):
        raise ValueError("ttl_seconds must be a number")
    normalized_ttl = None if ttl_seconds is None else normalize_session_ttl(ttl_seconds)

    image = payload.get("image")
    if image is not None and (not isinstance(image, str) or not image.strip()):
        raise ValueError("image must be a non-empty string")

    runtime_class = payload.get("runtime_class")
    if runtime_class is not None and (not isinstance(runtime_class, str) or not runtime_class.strip()):
        raise ValueError("runtime_class must be a non-empty string")

    return SessionCreateRequest(
        ttl_seconds=normalized_ttl,
        image=image.strip() if isinstance(image, str) else None,
        runtime_class=runtime_class.strip() if isinstance(runtime_class, str) else None,
    )


def parse_install_request(payload: Any) -> InstallRequest:
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")

    packages = payload.get("packages")
    if packages is None and "requirements" in payload:
        packages = payload["requirements"]

    if not isinstance(packages, list) or not packages:
        raise ValueError("packages must be a non-empty array")

    cleaned_packages = []
    for package in packages:
        if not isinstance(package, str):
            raise ValueError("packages must contain strings")
        cleaned_packages.append(package)

    return InstallRequest(packages=validate_requirements(cleaned_packages))


def _build_default_session_manager() -> SessionManager:
    root_dir = _env_text("SANDBOX_SESSION_ROOT")
    default_ttl_seconds = _env_float("SANDBOX_DEFAULT_TTL_SECONDS", 3600.0)
    backend_name = _env_text("SANDBOX_BACKEND_NAME", "local") or "local"
    default_image = _env_text("SANDBOX_IMAGE", "cloud-sandbox:latest") or "cloud-sandbox:latest"
    default_runtime_class = _env_text("SANDBOX_RUNTIME_CLASS", "gvisor") or "gvisor"
    return SessionManager(
        root_dir=root_dir,
        default_ttl_seconds=default_ttl_seconds,
        backend_name=backend_name,
        default_image=default_image,
        default_runtime_class=default_runtime_class,
    )


class SandboxAPI:
    def __init__(
        self,
        *,
        session_manager: SessionManager | None = None,
        auth_token: str | None = None,
    ) -> None:
        self.session_manager = session_manager or _build_default_session_manager()
        self.auth_token = auth_token

    def route(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        payload: Any | None,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        normalized_path = _normalize_path(path)
        try:
            if method == "GET":
                return self._handle_get(normalized_path, headers)
            if method == "POST":
                return self._handle_post(normalized_path, headers, payload)
            if method == "DELETE":
                return self._handle_delete(normalized_path, headers)
            return HTTPStatus.NOT_FOUND, {"error": "not found"}
        except AuthenticationError as exc:
            return HTTPStatus.UNAUTHORIZED, {"error": str(exc)}
        except ValueError as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc)}
        except KeyError as exc:
            message = exc.args[0] if exc.args else "not found"
            if not isinstance(message, str) or not message:
                message = "not found"
            return HTTPStatus.NOT_FOUND, {"error": message}
        except Exception:
            logger.exception("unexpected sandbox error")
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "sandbox request failed"}

    def _authorize(self, headers: Mapping[str, str]) -> None:
        require_bearer_auth(headers, self.auth_token)

    def _handle_get(self, path: str, headers: Mapping[str, str]) -> tuple[HTTPStatus, dict[str, Any]]:
        if path == "/health":
            return HTTPStatus.OK, {"status": "ok"}
        if path == "/":
            return HTTPStatus.OK, {
                "service": "cloud-sandbox",
                "status": "ok",
                "endpoints": [
                    "/health",
                    "/",
                    "/exec",
                    "/sessions",
                    "/sessions/{id}",
                    "/sessions/{id}/exec",
                    "/sessions/{id}/install",
                    "/sessions/{id}/artifacts",
                ],
            }

        self._authorize(headers)
        session_path = _split_session_path(path)
        if session_path is None:
            return HTTPStatus.NOT_FOUND, {"error": "not found"}

        session_id, action = session_path
        if action is None:
            return HTTPStatus.OK, session_to_dict(self.session_manager.get_session(session_id))
        if action == "artifacts":
            return HTTPStatus.OK, {
                "session_id": session_id,
                "artifact_paths": self.session_manager.get_artifacts(session_id),
            }
        return HTTPStatus.NOT_FOUND, {"error": "not found"}

    def _handle_post(
        self,
        path: str,
        headers: Mapping[str, str],
        payload: Any | None,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        if path == "/exec":
            self._authorize(headers)
            request = parse_exec_request(payload)
            result = execute_python(request)
            return HTTPStatus.OK, result_to_dict(result)

        if path == "/sessions":
            self._authorize(headers)
            request = parse_session_create_request(payload)
            session, created = self.session_manager.create_session(
                ttl_seconds=request.ttl_seconds,
                image=request.image,
                runtime_class=request.runtime_class,
                idempotency_key=_header_value(headers, "Idempotency-Key"),
            )
            status = HTTPStatus.CREATED if created else HTTPStatus.OK
            return status, {
                "created": created,
                "session": session_to_dict(session),
            }

        self._authorize(headers)
        session_path = _split_session_path(path)
        if session_path is None:
            return HTTPStatus.NOT_FOUND, {"error": "not found"}

        session_id, action = session_path
        if action == "exec":
            request = parse_exec_request(payload)
            session, result = self.session_manager.exec_code(session_id, request)
            return HTTPStatus.OK, {
                "session": session_to_dict(session),
                "result": result_to_dict(result),
            }
        if action == "install":
            request = parse_install_request(payload)
            session, result = self.session_manager.install_packages(session_id, request.packages)
            return HTTPStatus.OK, {
                "session": session_to_dict(session),
                "result": install_result_to_dict(result),
            }
        return HTTPStatus.NOT_FOUND, {"error": "not found"}

    def _handle_delete(self, path: str, headers: Mapping[str, str]) -> tuple[HTTPStatus, dict[str, Any]]:
        self._authorize(headers)
        session_path = _split_session_path(path)
        if session_path is None:
            return HTTPStatus.NOT_FOUND, {"error": "not found"}

        session_id, action = session_path
        if action is not None:
            return HTTPStatus.NOT_FOUND, {"error": "not found"}
        return HTTPStatus.OK, session_to_dict(self.session_manager.delete_session(session_id))


class SandboxHTTPRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    sandbox_api: SandboxAPI | None = None

    def do_GET(self) -> None:  # noqa: N802
        status, payload = self._route("GET", None)
        self._send_json(status, payload)

    def do_POST(self) -> None:  # noqa: N802
        status, payload = self._route("POST", self._read_json_body())
        self._send_json(status, payload)

    def do_DELETE(self) -> None:  # noqa: N802
        status, payload = self._route("DELETE", None)
        self._send_json(status, payload)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        logger.info("%s - %s", self.address_string(), format % args)

    def _route(self, method: str, payload: Any | None) -> tuple[HTTPStatus, dict[str, Any]]:
        if self.sandbox_api is None:
            raise RuntimeError("sandbox api is not configured")
        return self.sandbox_api.route(method, self.path, self.headers, payload)

    def _read_json_body(self) -> Any:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return None

        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON body") from exc

    def _send_json(
        self,
        status: HTTPStatus,
        payload: dict[str, Any],
    ) -> None:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        request_id = self.headers.get("X-Request-Id")
        if request_id:
            self.send_header("X-Request-Id", request_id)
        self.end_headers()
        self.wfile.write(body)


def create_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    *,
    session_manager: SessionManager | None = None,
    auth_token: str | None = None,
) -> ThreadingHTTPServer:
    api = SandboxAPI(session_manager=session_manager, auth_token=auth_token)

    class RequestHandler(SandboxHTTPRequestHandler):
        sandbox_api = api

    server = ThreadingHTTPServer((host, port), RequestHandler)
    server.sandbox_api = api  # type: ignore[attr-defined]
    return server


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    auth_token = _env_text("SANDBOX_AUTH_TOKEN")
    server = create_server(host=host, port=port, auth_token=auth_token)
    logger.info("cloud-sandbox listening on %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down")
    finally:
        sandbox_api = getattr(server, "sandbox_api", None)
        if sandbox_api is not None:
            sandbox_api.session_manager.close()
        server.server_close()
