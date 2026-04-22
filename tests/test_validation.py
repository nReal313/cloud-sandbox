from __future__ import annotations

import unittest

from cloud_sandbox.validation import (
    normalize_session_ttl,
    validate_env_name,
    validate_requirement,
    validate_requirements,
)


class ValidationTests(unittest.TestCase):
    def test_validate_requirement_accepts_normal_specs(self) -> None:
        self.assertEqual(validate_requirement("pandas==2.2.3"), "pandas==2.2.3")
        self.assertEqual(validate_requirement("pyarrow>=18.0"), "pyarrow>=18.0")

    def test_validate_requirement_rejects_unsafe_specs(self) -> None:
        for bad in ("", " ", "-r requirements.txt", "../escape", "pkg /tmp"):
            with self.assertRaises(ValueError):
                validate_requirement(bad)

        with self.assertRaises(ValueError):
            validate_requirements([])

    def test_validate_env_name_accepts_sandbox_safe_names(self) -> None:
        self.assertEqual(validate_env_name("FOO"), "FOO")
        self.assertEqual(validate_env_name("_PRIVATE"), "_PRIVATE")

    def test_validate_env_name_rejects_bad_names(self) -> None:
        for bad in ("", "1BAD", "BAD-NAME", "PIP_CACHE_DIR"):
            with self.assertRaises(ValueError):
                validate_env_name(bad)

    def test_normalize_session_ttl_rejects_invalid_values(self) -> None:
        self.assertEqual(normalize_session_ttl(None), 3600.0)
        with self.assertRaises(ValueError):
            normalize_session_ttl(0)
        with self.assertRaises(ValueError):
            normalize_session_ttl(float("nan"))
        with self.assertRaises(ValueError):
            normalize_session_ttl(24 * 60 * 60 + 1)


if __name__ == "__main__":
    unittest.main()
