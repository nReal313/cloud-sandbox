from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cloud_sandbox.models import ExecRequest
from cloud_sandbox.sessions import SessionManager


class SessionManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="cloud-sandbox-session-tests-")
        self.addCleanup(self.tempdir.cleanup)
        self.manager = SessionManager(root_dir=self.tempdir.name, default_ttl_seconds=60)
        self.addCleanup(self.manager.close)

    def test_create_exec_and_delete_session(self) -> None:
        session, created = self.manager.create_session(ttl_seconds=30)
        self.assertTrue(created)
        self.assertEqual(session.status, "active")

        session_after_exec, result = self.manager.exec_code(
            session.session_id,
            ExecRequest(
                code=(
                    "from pathlib import Path\n"
                    "Path('artifact.txt').write_text('done', encoding='utf-8')\n"
                    "print('hello from manager')\n"
                ),
                timeout_seconds=5,
            ),
        )

        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.timed_out)
        self.assertEqual(result.stdout, "hello from manager\n")
        self.assertIn("artifact.txt", result.artifact_paths)
        self.assertIn("artifact.txt", session_after_exec.artifact_paths)
        self.assertEqual(session_after_exec.last_exec_exit_code, 0)

        deleted = self.manager.delete_session(session.session_id)
        self.assertEqual(deleted.status, "deleted")

    def test_install_packages_updates_session_state(self) -> None:
        session, _ = self.manager.create_session(ttl_seconds=30)

        with patch.object(
            self.manager,
            "_run_subprocess",
            return_value=SimpleNamespace(stdout="installed\n", stderr="", exit_code=0, duration_ms=12),
        ):
            session_after_install, result = self.manager.install_packages(
                session.session_id,
                ["pandas==2.2.3"],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.packages, ["pandas==2.2.3"])
        self.assertIn("pandas==2.2.3", session_after_install.installed_packages)

    def test_install_packages_records_failures_without_raising(self) -> None:
        session, _ = self.manager.create_session(ttl_seconds=30)

        with patch.object(
            self.manager,
            "_run_subprocess",
            return_value=SimpleNamespace(stdout="", stderr="boom", exit_code=1, duration_ms=5),
        ):
            session_after_install, result = self.manager.install_packages(
                session.session_id,
                ["pandas==2.2.3"],
            )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("boom", session_after_install.last_error or "")
        self.assertEqual(session_after_install.installed_packages, [])


if __name__ == "__main__":
    unittest.main()
