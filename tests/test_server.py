from __future__ import annotations

import unittest

from cloud_sandbox.server import parse_exec_request


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

    def test_parse_exec_request_rejects_bad_payloads(self) -> None:
        with self.assertRaises(ValueError):
            parse_exec_request({"timeout_seconds": 1})

        with self.assertRaises(ValueError):
            parse_exec_request({"code": "", "timeout_seconds": 1})

        with self.assertRaises(ValueError):
            parse_exec_request({"code": "print(1)", "timeout_seconds": "soon"})

        with self.assertRaises(ValueError):
            parse_exec_request({"code": "print(1)", "timeout_seconds": 0})


if __name__ == "__main__":
    unittest.main()
