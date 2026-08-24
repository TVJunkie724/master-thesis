"""Offline regression tests for the setup-only live gate boundary."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from scripts.setup_only_live_gate import (
    ALLOWED_SETUP_OPERATIONS,
    CleanupLedgerStore,
    RESOURCE_KINDS,
    SetupGateError,
    add_owned_resource,
    attach_cloud_connection,
    authority_pack_gaps,
    create_manifest,
    new_cleanup_ledger,
    read_manifest,
    record_preflight_status,
    require_allowed_operation,
    require_setup_only_admission,
    transition_ledger,
    validate_cleanup_ledger,
    validate_manifest,
    write_manifest,
)


NOW = datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc)
RUN_ID = "twin2mc-e2e-a1b2c3d4"
AZURE_TENANT_ID = "11111111-1111-4111-8111-111111111111"
AZURE_SUBSCRIPTION_ID = "22222222-2222-4222-8222-222222222222"


def manifest(provider: str = "aws", mode: str = "setup_only"):
    targets = {
        "aws": {
            "provider": "aws",
            "account_id": "123456789012",
            "region": "eu-central-1",
        },
        "azure": {
            "provider": "azure",
            "tenant_id": AZURE_TENANT_ID,
            "subscription_id": AZURE_SUBSCRIPTION_ID,
            "region": "westeurope",
        },
        "gcp": {
            "provider": "gcp",
            "mode": "existing_project",
            "project_id": "twin2mc-test-project",
            "region": "europe-west1",
        },
    }
    return create_manifest(
        run_id=RUN_ID,
        provider=provider,
        mode=mode,
        target=targets[provider],
        created_at=NOW,
    )


class SetupGateManifestTests(unittest.TestCase):
    def test_all_provider_manifests_pin_real_pack_digests(self) -> None:
        for provider in ("aws", "azure", "gcp"):
            item = manifest(provider)
            self.assertEqual(item.provider, provider)
            self.assertEqual(
                item.document["deployment_pack"]["version"], "thesis-demo-v2"
            )
            if provider == "aws":
                self.assertEqual(
                    item.document["deployment_pack"]["id"],
                    "aws.thesis-demo-v2.iam-user-v1",
                )
            if provider == "azure":
                self.assertEqual(
                    item.document["deployment_pack"]["id"],
                    "azure.thesis-demo-v2.service-principal-v1",
                )
            if provider == "gcp":
                self.assertEqual(
                    item.document["deployment_pack"]["id"],
                    "gcp.thesis-demo-v2.service-account-v1",
                )
                self.assertEqual(
                    item.document["bootstrap_authority_pack"]["id"],
                    "bootstrap.gcp.admin-v3",
                )
                self.assertEqual(
                    item.document["api_baseline"]["id"],
                    "gcp.phase8-api-baseline.v1",
                )
                self.assertEqual(len(item.document["api_baseline"]["services"]), 19)
            else:
                self.assertIsNone(item.document["api_baseline"])
            self.assertRegex(
                item.document["bootstrap_authority_pack"]["digest"],
                r"^sha256:[a-f0-9]{64}$",
            )
            self.assertRegex(
                item.document["deployment_pack"]["digest"],
                r"^sha256:[a-f0-9]{64}$",
            )

    def test_manifest_rejects_extra_secret_shaped_fields(self) -> None:
        document = dict(manifest().document)
        document["secret_access_key"] = "sentinel"
        with self.assertRaisesRegex(SetupGateError, "extra=secret_access_key"):
            validate_manifest(document)

    def test_manifest_rejects_stale_pack_digest(self) -> None:
        document = json.loads(json.dumps(manifest().document))
        document["deployment_pack"]["digest"] = "sha256:" + ("0" * 64)
        with self.assertRaisesRegex(SetupGateError, "stale"):
            validate_manifest(document)

        document = json.loads(json.dumps(manifest("gcp").document))
        document["api_baseline"]["digest"] = "sha256:" + ("0" * 64)
        with self.assertRaisesRegex(SetupGateError, "stale"):
            validate_manifest(document)

    def test_wrong_provider_scope_and_gcp_organization_path_fail_closed(self) -> None:
        document = json.loads(json.dumps(manifest().document))
        document["target"]["provider"] = "gcp"
        with self.assertRaisesRegex(SetupGateError, "does not match"):
            validate_manifest(document)

        with self.assertRaisesRegex(SetupGateError, "existing_project only"):
            create_manifest(
                run_id=RUN_ID,
                provider="gcp",
                mode="setup_only",
                target={
                    "provider": "gcp",
                    "mode": "organization",
                    "project_id": "twin2mc-test-project",
                    "region": "europe-west1",
                },
                created_at=NOW,
            )

    def test_invalid_run_id_and_azure_scope_are_rejected(self) -> None:
        with self.assertRaisesRegex(SetupGateError, "Run ID"):
            create_manifest(
                run_id="production",
                provider="aws",
                mode="plan_only",
                target={
                    "provider": "aws",
                    "account_id": "123456789012",
                    "region": "eu-central-1",
                },
                created_at=NOW,
            )
        with self.assertRaisesRegex(SetupGateError, "Run ID"):
            create_manifest(
                run_id="twin2mc-e2e-abcdefghijklmnopqrstuvwxyz",
                provider="aws",
                mode="plan_only",
                target={
                    "provider": "aws",
                    "account_id": "123456789012",
                    "region": "eu-central-1",
                },
                created_at=NOW,
            )
        with self.assertRaisesRegex(SetupGateError, "UUID"):
            create_manifest(
                run_id=RUN_ID,
                provider="azure",
                mode="plan_only",
                target={
                    "provider": "azure",
                    "tenant_id": "wrong",
                    "subscription_id": AZURE_SUBSCRIPTION_ID,
                    "region": "westeurope",
                },
                created_at=NOW,
            )

    def test_plan_only_never_admits_provider_operations(self) -> None:
        item = manifest(mode="plan_only")
        with self.assertRaisesRegex(SetupGateError, "plan-only"):
            require_allowed_operation(item, "sts.get_caller_identity")
        with self.assertRaisesRegex(SetupGateError, "setup_only"):
            require_setup_only_admission(item, environment={})

    def test_live_admission_requires_two_exact_guards_and_forbids_ci(self) -> None:
        item = manifest()
        with self.assertRaisesRegex(SetupGateError, "not explicitly enabled"):
            require_setup_only_admission(item, environment={})
        with self.assertRaisesRegex(SetupGateError, "does not match"):
            require_setup_only_admission(
                item,
                environment={
                    "TWIN2MC_SETUP_GATE_ENABLED": "1",
                    "TWIN2MC_SETUP_GATE_CONFIRMATION": "wrong",
                },
            )
        with self.assertRaisesRegex(SetupGateError, "forbidden in CI"):
            require_setup_only_admission(
                item,
                environment={
                    "CI": "true",
                    "TWIN2MC_SETUP_GATE_ENABLED": "1",
                    "TWIN2MC_SETUP_GATE_CONFIRMATION": (f"{RUN_ID}:aws:setup_only"),
                },
            )

    def test_operation_allowlists_contain_no_workload_services(self) -> None:
        serialized = " ".join(
            operation
            for operations in ALLOWED_SETUP_OPERATIONS.values()
            for operation in operations
        )
        for forbidden in (
            "s3.",
            "lambda.",
            "iot.",
            "cosmos",
            "eventhub",
            "storage.",
            "container.",
            "run.services",
            "pubsub.",
        ):
            self.assertNotIn(forbidden, serialized)
        with self.assertRaisesRegex(SetupGateError, "outside"):
            require_allowed_operation(manifest(), "s3.create_bucket")

    def test_active_authority_packs_cover_setup_only_operations(self) -> None:
        for provider in ("aws", "azure", "gcp"):
            with self.subTest(provider=provider):
                self.assertEqual(authority_pack_gaps(provider), ())

    def test_azure_manifest_uses_versioned_v2_authority_pack(self) -> None:
        reference = manifest("azure").document["bootstrap_authority_pack"]

        self.assertEqual(reference["id"], "bootstrap.azure.admin-v2")
        self.assertEqual(reference["version"], "2")

    def test_aws_manifest_uses_managed_policy_v2_authority_pack(self) -> None:
        reference = manifest("aws").document["bootstrap_authority_pack"]

        self.assertEqual(reference["id"], "bootstrap.aws.admin-v2")
        self.assertEqual(reference["version"], "2")
        self.assertIn("managed_policy", RESOURCE_KINDS["aws"])
        self.assertNotIn("inline_policy", RESOURCE_KINDS["aws"])

    def test_azure_manifest_pins_service_principal_identity_binding(self) -> None:
        reference = manifest("azure").document["deployment_pack"]

        self.assertEqual(reference["id"], "azure.thesis-demo-v2.service-principal-v1")

    def test_gcp_manifest_uses_api_enablement_v3_authority_pack(self) -> None:
        reference = manifest("gcp").document["bootstrap_authority_pack"]

        self.assertEqual(reference["id"], "bootstrap.gcp.admin-v3")
        self.assertEqual(reference["version"], "3")
        self.assertIn("serviceusage.services.get", ALLOWED_SETUP_OPERATIONS["gcp"])
        self.assertIn(
            "serviceusage.services.batch_enable",
            ALLOWED_SETUP_OPERATIONS["gcp"],
        )
        self.assertIn("serviceusage.operations.get", ALLOWED_SETUP_OPERATIONS["gcp"])
        self.assertIn("iam.service_account_keys.get", ALLOWED_SETUP_OPERATIONS["gcp"])
        self.assertNotIn("iam.roles.list", ALLOWED_SETUP_OPERATIONS["gcp"])
        self.assertNotIn("iam.roles.update", ALLOWED_SETUP_OPERATIONS["gcp"])
        self.assertNotIn(
            "serviceusage.services.disable", ALLOWED_SETUP_OPERATIONS["gcp"]
        )


class CleanupLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = CleanupLedgerStore(self.root / "private" / "ledger.json")
        self.manifest = manifest()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_private_atomic_round_trip_and_clean_state(self) -> None:
        ledger = new_cleanup_ledger(self.manifest)
        self.store.create(ledger)
        self.assertEqual(stat.S_IMODE(self.store.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.store.path.parent.stat().st_mode), 0o700)

        ledger = transition_ledger(ledger, "authority_validated")
        ledger = add_owned_resource(
            ledger,
            kind="iam_user",
            provider_id="arn:aws:iam::123456789012:user/twin2mc-e2e-a1b2c3d4-user",
            owner_marker="twin2mc-e2e-a1b2c3d4-user",
        )
        ledger = transition_ledger(ledger, "identity_created")
        ledger = add_owned_resource(
            ledger,
            kind="access_key",
            provider_id="AKIATESTIDENTIFIER",
            owner_marker="twin2mc-e2e-a1b2c3d4-key",
        )
        ledger = transition_ledger(ledger, "credential_created")
        ledger = attach_cloud_connection(ledger, "connection-test-1")
        ledger = transition_ledger(ledger, "connection_persisted")
        ledger = record_preflight_status(ledger, "passed")
        ledger = transition_ledger(ledger, "preflight_passed")
        ledger = transition_ledger(ledger, "cleanup_required")
        ledger = transition_ledger(ledger, "cleanup_running")
        ledger = transition_ledger(ledger, "clean")
        self.store.save(ledger)

        loaded = self.store.load(manifest=self.manifest)
        self.assertTrue(loaded.is_clean)
        self.assertEqual(loaded.document["preflight_status"], "passed")
        self.store.require_no_stale_ledger()

    def test_stale_and_partial_failure_ledgers_block_next_run(self) -> None:
        ledger = new_cleanup_ledger(self.manifest)
        ledger = transition_ledger(ledger, "authority_validated")
        ledger = transition_ledger(ledger, "cleanup_required")
        self.store.create(ledger)
        with self.assertRaisesRegex(SetupGateError, "cleanup must finish"):
            self.store.require_no_stale_ledger()

    def test_wrong_owner_marker_and_secret_fields_are_rejected(self) -> None:
        ledger = new_cleanup_ledger(self.manifest)
        with self.assertRaisesRegex(SetupGateError, "while the ledger is planned"):
            add_owned_resource(
                ledger,
                kind="iam_user",
                provider_id="pre-existing-admin",
                owner_marker="twin2mc-e2e-a1b2c3d4-user",
            )
        ledger = transition_ledger(ledger, "authority_validated")
        with self.assertRaisesRegex(SetupGateError, "ownership marker"):
            add_owned_resource(
                ledger,
                kind="iam_user",
                provider_id="pre-existing-admin",
                owner_marker="unrelated-user",
            )

        document = dict(ledger.document)
        document["client_secret"] = "sentinel"
        with self.assertRaisesRegex(SetupGateError, "extra=client_secret"):
            validate_cleanup_ledger(document)

    def test_invalid_state_transition_fails_closed(self) -> None:
        ledger = new_cleanup_ledger(self.manifest)
        with self.assertRaisesRegex(SetupGateError, "cannot transition"):
            transition_ledger(ledger, "identity_created")

    def test_symlink_hardlink_and_public_permissions_are_rejected(self) -> None:
        self.store.path.parent.mkdir(mode=0o700)
        external = self.root / "external.json"
        external.write_text("{}", encoding="utf-8")
        self.store.path.symlink_to(external)
        with self.assertRaisesRegex(SetupGateError, "regular file"):
            self.store.load()
        self.store.path.unlink()

        os.link(external, self.store.path)
        with self.assertRaisesRegex(SetupGateError, "hard-linked"):
            self.store.load()
        self.store.path.unlink()

        ledger = new_cleanup_ledger(self.manifest)
        self.store.create(ledger)
        os.chmod(self.store.path, 0o644)
        with self.assertRaisesRegex(SetupGateError, "0600"):
            self.store.load()

    def test_existing_public_parent_is_rejected_without_permission_mutation(
        self,
    ) -> None:
        public_parent = self.root / "public"
        public_parent.mkdir(mode=0o755)
        public_store = CleanupLedgerStore(public_parent / "ledger.json")

        with self.assertRaisesRegex(SetupGateError, "0700"):
            public_store.create(new_cleanup_ledger(self.manifest))

        self.assertEqual(stat.S_IMODE(public_parent.stat().st_mode), 0o755)


class ManifestFileSafetyTests(unittest.TestCase):
    def test_manifest_round_trip_is_private_and_rejects_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "manifest.json"
            item = manifest()
            write_manifest(path, item)

            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(read_manifest(path).digest, item.digest)

            path.unlink()
            external = root / "external.json"
            write_manifest(external, item)
            path.symlink_to(external)
            with self.assertRaisesRegex(SetupGateError, "non-linked"):
                read_manifest(path)


if __name__ == "__main__":
    unittest.main()
