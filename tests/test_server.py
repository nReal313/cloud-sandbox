from __future__ import annotations

import tempfile
import unittest
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import patch

from cloud_sandbox.server import (
    SandboxAPI,
    parse_exec_request,
    parse_install_request,
    parse_session_create_request,
)
from cloud_sandbox.sessions import SessionManager


class ServerParsingTests(unittest.TestCase):
    def test_parse_exec_request(self) -> None:
        request = parse_exec_request(
            {
                "code": "print('sandbox ready')",
                "timeout_seconds": 5,
                "stdin": "input",
                "env": {"FOO": "bar"},
                "files": {"lib/helper.py": "x = 1\n"},
            }
        )

        self.assertEqual(request.code, "print('sandbox ready')")
        self.assertEqual(request.timeout_seconds, 5.0)
        self.assertEqual(request.stdin, "input")
        self.assertEqual(request.env["FOO"], "bar")
        self.assertEqual(request.files["lib/helper.py"], "x = 1\n")

    def test_parse_session_create_request(self) -> None:
        request = parse_session_create_request(
            {
                "ttl_seconds": 45,
                "image": "sandbox:latest",
                "runtime_class": "gvisor",
                "connectors": {
                    "gcp": {
                        "project_id": "sandbox-proj",
                        "bigquery_default_dataset": "analytics",
                        "gcs_bucket": "sandbox-bucket",
                        "firestore_collection": "session_metadata",
                    }
                },
            }
        )

        self.assertEqual(request.ttl_seconds, 45.0)
        self.assertEqual(request.image, "sandbox:latest")
        self.assertEqual(request.runtime_class, "gvisor")
        self.assertIsNotNone(request.connectors)
        self.assertIsNotNone(request.connectors.gcp)
        self.assertEqual(request.connectors.gcp.project_id, "sandbox-proj")

    def test_parse_session_create_request_rejects_bad_connectors(self) -> None:
        with self.assertRaises(ValueError):
            parse_session_create_request({"connectors": {"gcp": {"project_id": "bad id"}}})

    def test_parse_install_request_accepts_requirements_alias(self) -> None:
        request = parse_install_request({"requirements": ["pandas==2.2.3"]})

        self.assertEqual(request.packages, ["pandas==2.2.3"])

    def test_parse_exec_request_rejects_bad_payloads(self) -> None:
        with self.assertRaises(ValueError):
            parse_exec_request({"timeout_seconds": 1})

        with self.assertRaises(ValueError):
            parse_exec_request({"code": "", "timeout_seconds": 1})

        with self.assertRaises(ValueError):
            parse_exec_request({"code": "print(1)", "timeout_seconds": "soon"})

        with self.assertRaises(ValueError):
            parse_exec_request({"code": "print(1)", "timeout_seconds": 0})

        with self.assertRaises(ValueError):
            parse_exec_request({"code": "print(1)", "timeout_seconds": float("nan")})


class ServerRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="cloud-sandbox-tests-")
        self.addCleanup(self.tempdir.cleanup)
        self.manager = SessionManager(root_dir=self.tempdir.name, default_ttl_seconds=60)
        self.addCleanup(self.manager.close)
        self.api = SandboxAPI(session_manager=self.manager)

    def test_health_and_root_are_open(self) -> None:
        status, payload = self.api.route("GET", "/health", {}, None)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(payload["status"], "ok")

        status, payload = self.api.route("GET", "/", {}, None)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("/sessions", payload["endpoints"])

        status, payload = self.api.route("GET", "/capabilities", {}, None)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("gcp", payload["supported_connector_types"])

    def test_control_routes_are_open(self) -> None:
        status, payload = self.api.route("POST", "/sessions", {}, {})
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertTrue(payload["created"])

    def test_session_lifecycle_exec_install_artifacts_and_delete(self) -> None:
        status, payload = self.api.route(
            "POST",
            "/sessions",
            {},
            {
                "ttl_seconds": 30,
                "image": "sandbox:latest",
                "runtime_class": "gvisor",
                "connectors": {
                    "gcp": {
                        "project_id": "sandbox-proj",
                        "bigquery_default_dataset": "analytics",
                        "gcs_bucket": "sandbox-bucket",
                        "firestore_collection": "session_metadata",
                    }
                },
            },
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertTrue(payload["created"])
        session = payload["session"]
        session_id = session["session_id"]
        self.assertEqual(session["status"], "active")
        self.assertEqual(session["connectors"]["gcp"]["project_id"], "sandbox-proj")
        self.assertEqual(payload["capabilities"]["connectors"]["gcp"]["project_id"], "sandbox-proj")

        status, payload = self.api.route("GET", f"/sessions/{session_id}/capabilities", {}, None)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(payload["connectors"]["gcp"]["enabled"])
        self.assertEqual(payload["connectors"]["gcp"]["project_id"], "sandbox-proj")

        with patch.object(
            self.manager,
            "_run_subprocess",
            return_value=SimpleNamespace(stdout="installed\n", stderr="", exit_code=0, duration_ms=8),
        ):
            status, payload = self.api.route(
                "POST",
                f"/sessions/{session_id}/install",
                {},
                {"packages": ["pandas==2.2.3"]},
            )

        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("pandas==2.2.3", payload["session"]["installed_packages"])
        self.assertEqual(payload["result"]["exit_code"], 0)

        status, payload = self.api.route(
            "POST",
            f"/sessions/{session_id}/exec",
            {},
            {
                "code": (
                    "from pathlib import Path\n"
                    "Path('artifact.txt').write_text('done', encoding='utf-8')\n"
                    "print(sandbox.capabilities()['connectors']['gcp']['project_id'])\n"
                ),
                "timeout_seconds": 5,
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(payload["result"]["stdout"], "sandbox-proj\n")
        self.assertIn("artifact.txt", payload["result"]["artifact_paths"])

        status, payload = self.api.route("GET", f"/sessions/{session_id}", {}, None)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("artifact.txt", payload["artifact_paths"])
        self.assertEqual(payload["last_exec_exit_code"], 0)
        self.assertEqual(payload["connectors"]["gcp"]["project_id"], "sandbox-proj")

        status, payload = self.api.route("GET", f"/sessions/{session_id}/artifacts", {}, None)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("artifact.txt", payload["artifact_paths"])

        status, payload = self.api.route("DELETE", f"/sessions/{session_id}", {}, None)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(payload["status"], "deleted")

        status, payload = self.api.route("GET", f"/sessions/{session_id}", {}, None)
        self.assertEqual(status, HTTPStatus.NOT_FOUND)
        self.assertIn("session not found", payload["error"].lower())

    def test_create_session_is_idempotent_with_key(self) -> None:
        headers = {
            "Idempotency-Key": "create-1",
        }

        status, first = self.api.route("POST", "/sessions", headers, {"ttl_seconds": 15})
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertTrue(first["created"])

        status, second = self.api.route("POST", "/sessions", headers, {"ttl_seconds": 15})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertFalse(second["created"])
        self.assertEqual(first["session"]["session_id"], second["session"]["session_id"])


if __name__ == "__main__":
    unittest.main()
