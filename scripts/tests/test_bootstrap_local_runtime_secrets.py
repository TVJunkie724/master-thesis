"""Tests for the local CloudConnection encryption-key bootstrap."""

from __future__ import annotations

import base64
import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from scripts.bootstrap_local_runtime_secrets import (
    ENCRYPTION_KEY_FILENAME,
    SecretBootstrapError,
    bootstrap_local_runtime_secrets,
)


class LocalRuntimeSecretBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.secrets_dir = self.root / ".secrets" / "runtime"
        self.database = self.root / "data" / "app.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_fresh_bootstrap_creates_one_valid_private_key(self) -> None:
        result = bootstrap_local_runtime_secrets(
            self.secrets_dir, self.database, environment={}
        )

        value = self._read()
        self.assertEqual(result.statuses, {ENCRYPTION_KEY_FILENAME: "created"})
        self.assertEqual(len(base64.urlsafe_b64decode(value)), 32)
        self.assertEqual(stat.S_IMODE(self.secrets_dir.stat().st_mode), 0o700)
        self.assertEqual(
            stat.S_IMODE((self.secrets_dir / ENCRYPTION_KEY_FILENAME).stat().st_mode),
            0o600,
        )

    def test_second_bootstrap_preserves_the_key(self) -> None:
        bootstrap_local_runtime_secrets(self.secrets_dir, self.database, environment={})
        before = self._read()

        result = bootstrap_local_runtime_secrets(
            self.secrets_dir, self.database, environment={}
        )

        self.assertEqual(self._read(), before)
        self.assertEqual(result.statuses[ENCRYPTION_KEY_FILENAME], "preserved")

    def test_explicit_environment_key_is_imported(self) -> None:
        value = base64.urlsafe_b64encode(b"e" * 32).decode("ascii")
        result = bootstrap_local_runtime_secrets(
            self.secrets_dir,
            self.database,
            environment={ENCRYPTION_KEY_FILENAME: value},
        )

        self.assertEqual(self._read(), value)
        self.assertEqual(result.statuses[ENCRYPTION_KEY_FILENAME], "imported")

    def test_encrypted_rows_without_original_key_fail_before_mutation(self) -> None:
        self.database.parent.mkdir(parents=True)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "CREATE TABLE cloud_connections (id TEXT, encrypted_payload TEXT)"
            )
            connection.execute(
                "INSERT INTO cloud_connections VALUES ('connection-1', 'ciphertext')"
            )

        with self.assertRaisesRegex(SecretBootstrapError, "encrypted CloudConnections"):
            bootstrap_local_runtime_secrets(
                self.secrets_dir, self.database, environment={}
            )

        self.assertFalse((self.secrets_dir / ENCRYPTION_KEY_FILENAME).exists())

    def test_invalid_existing_key_is_never_replaced(self) -> None:
        self.secrets_dir.mkdir(parents=True)
        key_path = self.secrets_dir / ENCRYPTION_KEY_FILENAME
        key_path.write_text("short\n", encoding="utf-8")

        with self.assertRaisesRegex(SecretBootstrapError, ENCRYPTION_KEY_FILENAME):
            bootstrap_local_runtime_secrets(
                self.secrets_dir, self.database, environment={}
            )

        self.assertEqual(key_path.read_text(encoding="utf-8"), "short\n")

    def test_symlink_and_hard_link_targets_are_rejected(self) -> None:
        for use_symlink in (True, False):
            with self.subTest(use_symlink=use_symlink):
                target_dir = self.root / f"runtime-{use_symlink}"
                target_dir.mkdir()
                external = self.root / f"external-{use_symlink}"
                external.write_text("e" * 44, encoding="utf-8")
                target = target_dir / ENCRYPTION_KEY_FILENAME
                if use_symlink:
                    target.symlink_to(external)
                else:
                    os.link(external, target)

                with self.assertRaises(SecretBootstrapError):
                    bootstrap_local_runtime_secrets(
                        target_dir, self.database, environment={}
                    )

    def test_existing_permissions_are_normalized(self) -> None:
        bootstrap_local_runtime_secrets(self.secrets_dir, self.database, environment={})
        os.chmod(self.secrets_dir, 0o777)
        os.chmod(self.secrets_dir / ENCRYPTION_KEY_FILENAME, 0o666)

        bootstrap_local_runtime_secrets(self.secrets_dir, self.database, environment={})

        self.assertEqual(stat.S_IMODE(self.secrets_dir.stat().st_mode), 0o700)
        self.assertEqual(
            stat.S_IMODE((self.secrets_dir / ENCRYPTION_KEY_FILENAME).stat().st_mode),
            0o600,
        )

    def _read(self) -> str:
        return (
            (self.secrets_dir / ENCRYPTION_KEY_FILENAME)
            .read_text(encoding="utf-8")
            .strip()
        )


if __name__ == "__main__":
    unittest.main()
