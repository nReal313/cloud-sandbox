from __future__ import annotations

import unittest

from cloud_sandbox.executor import execute_python
from cloud_sandbox.models import ExecRequest


class ExecutorTests(unittest.TestCase):
    def test_execute_python_returns_stdout_and_artifacts(self) -> None:
        request = ExecRequest(
            code=(
                "from pathlib import Path\n"
                "Path('artifact.txt').write_text('done', encoding='utf-8')\n"
                "print('hello')\n"
            ),
            timeout_seconds=5,
        )

        result = execute_python(request)

        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.timed_out)
        self.assertEqual(result.stdout, "hello\n")
        self.assertIn("artifact.txt", result.artifact_paths)

    def test_execute_python_times_out(self) -> None:
        request = ExecRequest(
            code="import time\nwhile True:\n    time.sleep(0.1)\n",
            timeout_seconds=0.5,
        )

        result = execute_python(request)

        self.assertEqual(result.exit_code, 124)
        self.assertTrue(result.timed_out)
        self.assertIn("timeout", result.stderr.lower())

    def test_rejects_escape_paths(self) -> None:
        request = ExecRequest(code="print('ok')", files={"../escape.txt": "nope"})

        with self.assertRaises(ValueError):
            execute_python(request)


if __name__ == "__main__":
    unittest.main()

