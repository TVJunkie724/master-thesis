"""Tests for the dependency-free local runtime secret bootstrap."""

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
    JWT_SECRET_FILENAME,
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

    def test_fresh_bootstrap_creates_distinct_valid_private_files(self) -> None:
        result = bootstrap_local_runtime_secrets(
            self.secrets_dir,
            self.database,
            environment={},
        )

        jwt_value = self._read(JWT_SECRET_FILENAME)
        encryption_value = self._read(ENCRYPTION_KEY_FILENAME)
        self.assertEqual(result.statuses[JWT_SECRET_FILENAME], "created")
        self.assertEqual(result.statuses[ENCRYPTION_KEY_FILENAME], "created")
        self.assertNotEqual(jwt_value, encryption_value)
        self.assertGreaterEqual(len(jwt_value), 32)
        self.assertEqual(len(base64.urlsafe_b64decode(encryption_value)), 32)
        self.assertEqual(stat.S_IMODE(self.secrets_dir.stat().st_mode), 0o700)
        self.assertEqual(
            stat.S_IMODE((self.secrets_dir / JWT_SECRET_FILENAME).stat().st_mode),
            0o600,
        )
        self.assertEqual(
            stat.S_IMODE((self.secrets_dir / ENCRYPTION_KEY_FILENAME).stat().st_mode),
            0o600,
        )

    def test_second_bootstrap_preserves_values_byte_for_byte(self) -> None:
        bootstrap_local_runtime_secrets(self.secrets_dir, self.database, environment={})
        before = {name: (self.secrets_dir / name).read_bytes() for name in self._names()}

        result = bootstrap_local_runtime_secrets(
            self.secrets_dir,
            self.database,
            environment={},
        )

        after = {name: (self.secrets_dir / name).read_bytes() for name in self._names()}
        self.assertEqual(after, before)
        self.assertEqual(set(result.statuses.values()), {"preserved"})

    def test_explicit_environment_values_are_imported(self) -> None:
        jwt_value = "j" * 64
        encryption_value = base64.urlsafe_b64encode(b"e" * 32).decode("ascii")

        result = bootstrap_local_runtime_secrets(
            self.secrets_dir,
            self.database,
            environment={
                JWT_SECRET_FILENAME: jwt_value,
                ENCRYPTION_KEY_FILENAME: encryption_value,
            },
        )

        self.assertEqual(self._read(JWT_SECRET_FILENAME), jwt_value)
        self.assertEqual(self._read(ENCRYPTION_KEY_FILENAME), encryption_value)
        self.assertEqual(set(result.statuses.values()), {"imported"})

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
                self.secrets_dir,
                self.database,
                environment={},
            )

        self.assertFalse((self.secrets_dir / JWT_SECRET_FILENAME).exists())
        self.assertFalse((self.secrets_dir / ENCRYPTION_KEY_FILENAME).exists())

    def test_existing_invalid_secret_fails_without_replacement(self) -> None:
        self.secrets_dir.mkdir(parents=True)
        invalid_path = self.secrets_dir / JWT_SECRET_FILENAME
        invalid_path.write_text("short\n", encoding="utf-8")

        with self.assertRaisesRegex(SecretBootstrapError, JWT_SECRET_FILENAME):
            bootstrap_local_runtime_secrets(
                self.secrets_dir,
                self.database,
                environment={},
            )

        self.assertEqual(invalid_path.read_text(encoding="utf-8"), "short\n")
        self.assertFalse((self.secrets_dir / ENCRYPTION_KEY_FILENAME).exists())

    def test_known_placeholder_and_duplicate_values_fail_closed(self) -> None:
        encryption_value = base64.urlsafe_b64encode(b"x" * 32).decode("ascii")
        with self.assertRaisesRegex(SecretBootstrapError, "known insecure placeholder"):
            bootstrap_local_runtime_secrets(
                self.secrets_dir,
                self.database,
                environment={
                    JWT_SECRET_FILENAME: "local-development-jwt-secret-change-me",
                    ENCRYPTION_KEY_FILENAME: encryption_value,
                },
            )

        duplicate = base64.urlsafe_b64encode(b"d" * 32).decode("ascii")
        with self.assertRaisesRegex(SecretBootstrapError, "must be different"):
            bootstrap_local_runtime_secrets(
                self.secrets_dir,
                self.database,
                environment={
                    JWT_SECRET_FILENAME: duplicate,
                    ENCRYPTION_KEY_FILENAME: duplicate,
                },
            )

    def test_malformed_encryption_key_and_control_character_fail(self) -> None:
        with self.assertRaisesRegex(SecretBootstrapError, "URL-safe base64"):
            bootstrap_local_runtime_secrets(
                self.secrets_dir,
                self.database,
                environment={
                    JWT_SECRET_FILENAME: "j" * 64,
                    ENCRYPTION_KEY_FILENAME: "!" * 44,
                },
            )

        with self.assertRaisesRegex(SecretBootstrapError, "control characters"):
            bootstrap_local_runtime_secrets(
                self.secrets_dir,
                self.database,
                environment={
                    JWT_SECRET_FILENAME: ("j" * 20) + "\t" + ("j" * 20),
                    ENCRYPTION_KEY_FILENAME: base64.urlsafe_b64encode(b"e" * 32).decode(
                        "ascii"
                    ),
                },
            )

        with self.assertRaisesRegex(SecretBootstrapError, "surrounding whitespace"):
            bootstrap_local_runtime_secrets(
                self.secrets_dir,
                self.database,
                environment={
                    JWT_SECRET_FILENAME: ("j" * 64) + " ",
                    ENCRYPTION_KEY_FILENAME: base64.urlsafe_b64encode(b"e" * 32).decode(
                        "ascii"
                    ),
                },
            )

        standard_base64 = base64.b64encode(bytes([251]) * 32).decode("ascii")
        self.assertIn("+", standard_base64)
        with self.assertRaisesRegex(SecretBootstrapError, "URL-safe base64"):
            bootstrap_local_runtime_secrets(
                self.secrets_dir,
                self.database,
                environment={
                    JWT_SECRET_FILENAME: "j" * 64,
                    ENCRYPTION_KEY_FILENAME: standard_base64,
                },
            )

    def test_symlink_target_is_rejected_without_modifying_target(self) -> None:
        self.secrets_dir.mkdir(parents=True)
        external = self.root / "external"
        external.write_text("j" * 64, encoding="utf-8")
        (self.secrets_dir / JWT_SECRET_FILENAME).symlink_to(external)

        with self.assertRaisesRegex(SecretBootstrapError, "regular file"):
            bootstrap_local_runtime_secrets(
                self.secrets_dir,
                self.database,
                environment={},
            )

        self.assertEqual(external.read_text(encoding="utf-8"), "j" * 64)

    def test_hard_linked_secret_is_rejected_without_modifying_source(self) -> None:
        self.secrets_dir.mkdir(parents=True)
        external = self.root / "external"
        external.write_text("j" * 64, encoding="utf-8")
        os.link(external, self.secrets_dir / JWT_SECRET_FILENAME)

        with self.assertRaisesRegex(SecretBootstrapError, "hard-linked"):
            bootstrap_local_runtime_secrets(
                self.secrets_dir,
                self.database,
                environment={},
            )

        self.assertEqual(external.read_text(encoding="utf-8"), "j" * 64)

    def test_partial_pair_creation_is_rolled_back(self) -> None:
        calls = 0

        def failing_creator(path: Path, value: str) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic failure")
            path.write_text(f"{value}\n", encoding="utf-8")

        with self.assertRaisesRegex(SecretBootstrapError, "complete local runtime"):
            bootstrap_local_runtime_secrets(
                self.secrets_dir,
                self.database,
                environment={},
                create_secret_file=failing_creator,
            )

        self.assertFalse((self.secrets_dir / JWT_SECRET_FILENAME).exists())
        self.assertFalse((self.secrets_dir / ENCRYPTION_KEY_FILENAME).exists())

    def test_existing_permissions_are_normalized(self) -> None:
        bootstrap_local_runtime_secrets(self.secrets_dir, self.database, environment={})
        os.chmod(self.secrets_dir, 0o777)
        for name in self._names():
            os.chmod(self.secrets_dir / name, 0o666)

        bootstrap_local_runtime_secrets(self.secrets_dir, self.database, environment={})

        self.assertEqual(stat.S_IMODE(self.secrets_dir.stat().st_mode), 0o700)
        for name in self._names():
            self.assertEqual(stat.S_IMODE((self.secrets_dir / name).stat().st_mode), 0o600)

    def test_existing_parent_directory_permissions_are_not_modified(self) -> None:
        shared_parent = self.root / "shared"
        shared_parent.mkdir(mode=0o755)
        os.chmod(shared_parent, 0o755)

        bootstrap_local_runtime_secrets(
            shared_parent / "runtime",
            self.database,
            environment={},
        )

        self.assertEqual(stat.S_IMODE(shared_parent.stat().st_mode), 0o755)

    def test_symlinked_database_is_rejected_before_secret_creation(self) -> None:
        self.database.parent.mkdir(parents=True)
        self.database.symlink_to(self.root / "missing-database")

        with self.assertRaisesRegex(SecretBootstrapError, "regular file"):
            bootstrap_local_runtime_secrets(
                self.secrets_dir,
                self.database,
                environment={},
            )

        self.assertFalse((self.secrets_dir / JWT_SECRET_FILENAME).exists())
        self.assertFalse((self.secrets_dir / ENCRYPTION_KEY_FILENAME).exists())

    def _read(self, filename: str) -> str:
        return (self.secrets_dir / filename).read_text(encoding="utf-8").strip()

    @staticmethod
    def _names() -> tuple[str, str]:
        return JWT_SECRET_FILENAME, ENCRYPTION_KEY_FILENAME


if __name__ == "__main__":
    unittest.main()
