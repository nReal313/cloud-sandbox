from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .executor import execute_python
from .models import ExecRequest, result_to_dict

logger = logging.getLogger(__name__)


class SandboxHTTPRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/":
            self._send_json(
                HTTPStatus.OK,
                {
                    "service": "cloud-sandbox",
                    "endpoints": ["/health", "/exec"],
                    "status": "ok",
                },
            )
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/exec":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        try:
            request = self._read_exec_request()
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        try:
            result = execute_python(request)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except Exception:
            logger.exception("execution failed unexpectedly")
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "execution failed"})
            return

        self._send_json(HTTPStatus.OK, result_to_dict(result))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        logger.info("%s - %s", self.address_string(), format % args)

    def _read_exec_request(self) -> ExecRequest:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("request body is required")

        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON body") from exc

        return parse_exec_request(payload)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), SandboxHTTPRequestHandler)


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = create_server(host=host, port=port)
    logger.info("cloud-sandbox listening on %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down")
    finally:
        server.server_close()


def parse_exec_request(payload: Any) -> ExecRequest:
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")

    code = payload.get("code")
    if not isinstance(code, str) or not code.strip():
        raise ValueError("code must be a non-empty string")

    timeout_seconds = payload.get("timeout_seconds", 10.0)
    if not isinstance(timeout_seconds, (int, float)):
        raise ValueError("timeout_seconds must be a number")
    if float(timeout_seconds) <= 0:
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
        timeout_seconds=float(timeout_seconds),
        stdin=stdin,
        env=cleaned_env,
        files=cleaned_files,
    )
