"""Regression tests for architecture-profile contracts and service parity."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any

from jsonschema import Draft202012Validator

from scripts import sync_architecture_profile_contracts as contract_sync


ROOT = contract_sync.ROOT


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ArchitectureProfileContractSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.valid_documents = contract_sync.load_valid_documents()
        cls.profile = contract_sync._read_json(
            contract_sync.VALID_ROOT / "five-layer-baseline-profile.json"
        )
        cls.catalog = contract_sync._read_json(
            contract_sync.VALID_ROOT / "baseline-component-catalog.json"
        )
        cls.service_modules = (
            _load_module(
                "_golden_optimizer_architecture_contracts",
                ROOT
                / "2-twin2clouds"
                / "backend"
                / "architecture_profiles"
                / "contracts.py",
            ),
            _load_module(
                "_golden_management_architecture_contracts",
                ROOT
                / "twin2multicloud_backend"
                / "src"
                / "services"
                / "architecture_contract_service.py",
            ),
            _load_module(
                "_golden_deployer_architecture_contracts",
                ROOT
                / "3-cloud-deployer"
                / "src"
                / "architecture_profiles"
                / "contracts.py",
            ),
        )

    def test_source_and_generated_copies_are_valid_and_identical(self) -> None:
        contract_sync.validate_source()
        contract_sync.check_synchronized()

    def test_required_fixture_matrix_is_exact(self) -> None:
        valid_names = {path.name for path in contract_sync.VALID_ROOT.glob("*.json")}
        invalid_names = {
            path.name for path in contract_sync.INVALID_ROOT.glob("*.json")
        }
        self.assertTrue(contract_sync.MANDATORY_VALID_FIXTURES <= valid_names)
        self.assertEqual(
            invalid_names,
            set(contract_sync.MANDATORY_INVALID_FIXTURES),
        )

    def test_each_valid_document_and_linked_bundle_are_accepted(self) -> None:
        for document in self.valid_documents:
            validated = contract_sync.runtime.validate_document(
                document,
                bundle_root=contract_sync.SOURCE_V1,
                linked_documents=self.valid_documents,
            )
            self.assertEqual(validated.content_digest, document["content_digest"])
        validated_bundle = contract_sync.runtime.validate_bundle(
            self.valid_documents,
            bundle_root=contract_sync.SOURCE_V1,
        )
        self.assertEqual(len(validated_bundle), len(self.valid_documents))

    def test_resolution_accepts_management_owned_uuid_artifact_ids(self) -> None:
        resolution = next(
            copy.deepcopy(document)
            for document in self.valid_documents
            if document["schema_version"] == "resolved-twin-architecture.v1"
        )
        resolution["extension_bindings"][0]["artifact_id"] = (
            "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a02"
        )
        resolution["resolution_id"] = (
            contract_sync.runtime.calculate_resolution_id(resolution)
        )
        contract_sync._redigest(resolution)

        validated = contract_sync.runtime.validate_document(
            resolution,
            bundle_root=contract_sync.SOURCE_V1,
            linked_documents=self.valid_documents,
        )

        self.assertEqual(
            validated.document["extension_bindings"][0]["artifact_id"],
            "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a02",
        )

    def test_negative_fixtures_fail_with_stable_codes(self) -> None:
        for path in sorted(contract_sync.INVALID_ROOT.glob("*.json")):
            wrapper = contract_sync._read_json(path)
            with self.assertRaises(contract_sync.runtime.ContractError) as raised:
                contract_sync.runtime.validate_document(
                    wrapper["document"],
                    bundle_root=contract_sync.SOURCE_V1,
                    linked_documents=self.valid_documents,
                )
            self.assertEqual(raised.exception.code, wrapper["expected_error"])
            self.assertLessEqual(len(str(raised.exception)), 400)

    def test_all_services_accept_with_identical_digest(self) -> None:
        expected = self.profile["content_digest"]
        digests = []
        for index, module in enumerate(self.service_modules):
            if index == 1:
                validated = module.ArchitectureContractService.read(
                    self.profile,
                    linked_documents=self.valid_documents,
                )
            else:
                validated = module.read_contract(
                    self.profile,
                    linked_documents=self.valid_documents,
                )
            digests.append(validated.content_digest)
        self.assertEqual(digests, [expected, expected, expected])

    def test_all_services_reject_with_identical_codes(self) -> None:
        for path in sorted(contract_sync.INVALID_ROOT.glob("*.json")):
            wrapper = contract_sync._read_json(path)
            codes = []
            for index, module in enumerate(self.service_modules):
                try:
                    if index == 1:
                        module.ArchitectureContractService.read(
                            wrapper["document"],
                            linked_documents=self.valid_documents,
                        )
                    else:
                        module.read_contract(
                            wrapper["document"],
                            linked_documents=self.valid_documents,
                        )
                except module.ContractError as exc:
                    codes.append(exc.code)
                else:
                    self.fail(f"{path.name} passed in service reader {index}")
            self.assertEqual(codes, [wrapper["expected_error"]] * 3)

    def test_every_top_level_required_field_fails_closed_when_absent(self) -> None:
        documents_by_version = {
            document["schema_version"]: document for document in self.valid_documents
        }
        documents_by_version["semantic-registry.v1"] = contract_sync._read_json(
            contract_sync.SOURCE_V1 / "semantic-registry.json"
        )
        for version, filename in contract_sync.runtime.SCHEMA_FILES.items():
            schema = contract_sync._read_json(contract_sync.SOURCE_V1 / filename)
            for field in schema["required"]:
                mutated = copy.deepcopy(documents_by_version[version])
                del mutated[field]
                with self.assertRaises(contract_sync.runtime.ContractError):
                    contract_sync.runtime.validate_document(
                        mutated,
                        bundle_root=contract_sync.SOURCE_V1,
                        linked_documents=self.valid_documents,
                    )

    def test_every_represented_nested_required_field_fails_closed(self) -> None:
        schemas = {
            version: contract_sync._read_json(contract_sync.SOURCE_V1 / filename)
            for version, filename in contract_sync.runtime.SCHEMA_FILES.items()
        }
        documents_by_version = {
            document["schema_version"]: document for document in self.valid_documents
        }
        documents_by_version["semantic-registry.v1"] = contract_sync._read_json(
            contract_sync.SOURCE_V1 / "semantic-registry.json"
        )

        def resolve(
            reference: str,
            base_schema: dict[str, Any],
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            filename, _, fragment = reference.partition("#")
            target_schema = base_schema
            if filename:
                target_schema = next(
                    schema
                    for schema in schemas.values()
                    if schema["$id"].endswith(filename)
                )
            target: Any = target_schema
            if fragment:
                for part in fragment.removeprefix("/").split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            return target, target_schema

        def represented_required_paths(
            schema: dict[str, Any],
            instance: Any,
            path: tuple[object, ...] = (),
            base_schema: dict[str, Any] | None = None,
        ):
            base = base_schema or schema
            if "$ref" in schema:
                target, target_base = resolve(schema["$ref"], base)
                yield from represented_required_paths(
                    target,
                    instance,
                    path,
                    target_base,
                )
                return
            if isinstance(instance, dict):
                for field in schema.get("required", []):
                    if field in instance:
                        yield (*path, field)
                for field, nested in instance.items():
                    child_schema = schema.get("properties", {}).get(field)
                    if isinstance(child_schema, dict):
                        yield from represented_required_paths(
                            child_schema,
                            nested,
                            (*path, field),
                            base,
                        )
            elif isinstance(instance, list) and instance:
                item_schema = schema.get("items")
                if isinstance(item_schema, dict):
                    yield from represented_required_paths(
                        item_schema,
                        instance[0],
                        (*path, 0),
                        base,
                    )

        def delete_path(document: dict[str, Any], path: tuple[object, ...]) -> None:
            parent: Any = document
            for part in path[:-1]:
                parent = parent[part]
            del parent[path[-1]]

        for version, document in documents_by_version.items():
            paths = sorted(
                set(represented_required_paths(schemas[version], document)),
                key=lambda path: tuple(str(part) for part in path),
            )
            self.assertGreater(len(paths), len(schemas[version]["required"]))
            for path in paths:
                mutated = copy.deepcopy(document)
                delete_path(mutated, path)
                with self.subTest(version=version, path=path):
                    with self.assertRaises(contract_sync.runtime.ContractError):
                        contract_sync.runtime.validate_document(
                            mutated,
                            bundle_root=contract_sync.SOURCE_V1,
                            linked_documents=self.valid_documents,
                        )

    def test_empty_baseline_object_definitions_enforce_required_and_closed(
        self,
    ) -> None:
        schemas, schema_registry = contract_sync.runtime._load_schemas(
            contract_sync.SOURCE_V1
        )
        cases = (
            (
                "architecture-profile.v1",
                "extension_slot",
                {
                    "slot_id": "slot.processor",
                    "slot_version": "1",
                    "component_id": "component.processing",
                    "input_contract_ref": {
                        "id": "normalized-telemetry",
                        "version": "1",
                    },
                    "output_contract_ref": {
                        "id": "processed-telemetry",
                        "version": "1",
                    },
                    "configuration_contract_ref": {
                        "id": "processor-configuration",
                        "version": "1",
                    },
                    "artifact_policy_id": "artifact-policy.user-function",
                },
            ),
            (
                "provider-implementation-profile.v1",
                "unsupported_reason",
                {
                    "reason_code": "reason.capability-unavailable",
                    "message": "Required capability is unavailable.",
                },
            ),
            (
                "resolved-twin-architecture.v1",
                "extension_binding",
                {
                    "slot_id": "slot.processor",
                    "slot_version": "1",
                    "artifact_id": "artifact.user.processor",
                    "artifact_digest": f"sha256:{'1' * 64}",
                    "logical_component_id": "component.processing",
                    "configuration_digest": f"sha256:{'2' * 64}",
                    "validation_contract_version": "1",
                },
            ),
        )
        for version, definition_name, sample in cases:
            parent = schemas[version]
            definition = {
                "$schema": parent["$schema"],
                "$id": parent["$id"],
                **parent["$defs"][definition_name],
            }
            validator = Draft202012Validator(
                definition,
                registry=schema_registry,
            )
            self.assertEqual(list(validator.iter_errors(sample)), [])
            for field in definition["required"]:
                mutated = copy.deepcopy(sample)
                del mutated[field]
                with self.subTest(definition=definition_name, field=field):
                    self.assertTrue(list(validator.iter_errors(mutated)))
            additional = copy.deepcopy(sample)
            additional["unexpected"] = True
            self.assertTrue(list(validator.iter_errors(additional)))

    def test_every_schema_object_is_closed(self) -> None:
        findings = []
        for filename in contract_sync.SCHEMA_FILES:
            schema = contract_sync._read_json(contract_sync.SOURCE_V1 / filename)

            def walk(value: object, path: str = "$") -> None:
                if isinstance(value, dict):
                    if (
                        value.get("type") == "object"
                        and value.get("additionalProperties") is not False
                    ):
                        findings.append(f"{filename}:{path}")
                    for key, nested in value.items():
                        walk(nested, f"{path}.{key}")
                elif isinstance(value, list):
                    for index, nested in enumerate(value):
                        walk(nested, f"{path}[{index}]")

            walk(schema)
        self.assertEqual(findings, [])

    def test_loader_size_depth_and_array_limits_fail_closed(self) -> None:
        oversized = copy.deepcopy(self.profile)
        oversized["description"] = "x" * contract_sync.runtime.MAX_DOCUMENT_BYTES
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                oversized,
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_SCHEMA_INVALID")

        overdeep = copy.deepcopy(self.profile)
        nested: dict[str, Any] = {}
        overdeep["debug"] = nested
        for _ in range(contract_sync.runtime.MAX_DEPTH + 2):
            child: dict[str, Any] = {}
            nested["child"] = child
            nested = child
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                overdeep,
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_SCHEMA_INVALID")

        overlong = copy.deepcopy(self.profile)
        overlong["compatibility"]["supported_contract_versions"] = [
            f"contract-{index}"
            for index in range(contract_sync.runtime.MAX_ARRAY_ITEMS + 1)
        ]
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                overlong,
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_SCHEMA_INVALID")

    def test_additional_property_fails_closed(self) -> None:
        mutated = copy.deepcopy(self.profile)
        mutated["debug_mode"] = True
        contract_sync._redigest(mutated)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                mutated,
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_SCHEMA_INVALID")

    def test_digest_is_stable_for_set_order_and_decimal_normalization(self) -> None:
        reordered = copy.deepcopy(self.profile)
        reordered["components"].reverse()
        reordered["responsibilities"].reverse()
        self.assertEqual(
            contract_sync.runtime.calculate_digest(reordered),
            self.profile["content_digest"],
        )
        self.assertEqual(
            contract_sync.runtime.canonical_json({"amount": "1.00"}),
            contract_sync.runtime.canonical_json({"amount": "1"}),
        )
        self.assertNotEqual(
            contract_sync.runtime.canonical_json(
                {
                    "deployment_component_candidates": [
                        "deployment.aws.second",
                        "deployment.aws.first",
                    ]
                }
            ),
            contract_sync.runtime.canonical_json(
                {
                    "deployment_component_candidates": [
                        "deployment.aws.first",
                        "deployment.aws.second",
                    ]
                }
            ),
        )

    def test_workload_and_responsibility_coupling_fail_closed(self) -> None:
        workload_mutation = copy.deepcopy(self.profile)
        workload_mutation["workload_contract_ref"]["id"] = "other-workload"
        contract_sync._redigest(workload_mutation)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                workload_mutation,
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_BUNDLE_INCOMPATIBLE")

        responsibility_mutation = copy.deepcopy(self.profile)
        responsibility_mutation["responsibilities"][0]["logical_component_ids"] = [
            "component.processing"
        ]
        contract_sync._redigest(responsibility_mutation)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                responsibility_mutation,
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_REFERENCE_UNRESOLVED")

    def test_resolution_optimization_bundle_must_match_profile(self) -> None:
        resolution = next(
            document
            for document in self.valid_documents
            if document["schema_version"] == "resolved-twin-architecture.v1"
        )
        mutated = copy.deepcopy(resolution)
        mutated["optimization_bundle_ref"]["formula_set_version"] = "2"
        mutated["resolution_id"] = (
            contract_sync.runtime.calculate_resolution_id(mutated)
        )
        contract_sync._redigest(mutated)

        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                mutated,
                bundle_root=contract_sync.SOURCE_V1,
                linked_documents=self.valid_documents,
            )
        self.assertEqual(raised.exception.code, "ARCH_BUNDLE_INCOMPATIBLE")

    def test_allowlisted_cycle_requires_exact_registered_scc(self) -> None:
        cycle_profile = copy.deepcopy(self.profile)
        cycle_profile["edges"].append(
            {
                "edge_id": "edge.twin-state-to-hot-storage-cycle",
                "source_component_id": "component.twin-state",
                "source_port_id": "port.twin-state.query-out",
                "destination_component_id": "component.hot-storage",
                "destination_port_id": "port.hot-storage.write-in",
                "edge_contract_id": "twin-query-result",
                "edge_contract_version": "1",
                "required": True,
                "delivery_requirements": contract_sync._delivery_requirements(
                    "synchronous"
                ),
                "trust_requirements": {
                    "authentication": "workload_identity",
                    "authorization": "least_privilege_capability_set",
                    "transport": "tls",
                },
                "observability_requirements": {
                    "correlation": "required",
                    "metrics": "required",
                    "bounded_error_contract": "required",
                },
                "transfer_workload_ref": {
                    "id": "logical-query-count",
                    "version": "1",
                },
                "cost_owner_ids": ["cost.twin-state-to-hot-storage-cycle"],
            }
        )
        cycle_profile["graph_policy"] = {
            "cycle_policy": "allowlisted",
            "allowed_cycle_ids": ["cycle.hot-storage.twin-state"],
            "optional_components": [],
            "user_topology_editable": False,
        }
        contract_sync._redigest(cycle_profile)
        validated = contract_sync.runtime.validate_document(
            cycle_profile,
            bundle_root=contract_sync.SOURCE_V1,
        )
        self.assertEqual(validated.stable_id, "five-layer-baseline")

        cycle_profile["graph_policy"]["allowed_cycle_ids"] = ["cycle.unregistered"]
        contract_sync._redigest(cycle_profile)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                cycle_profile,
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_GRAPH_CYCLE_FORBIDDEN")

    def test_digest_changes_for_every_contract_mutation(self) -> None:
        for document in self.valid_documents:
            mutated = copy.deepcopy(document)
            if "description" in mutated:
                mutated["description"] += " changed"
            elif "lifecycle_status" in mutated:
                mutated["lifecycle_status"] = "deprecated"
            else:
                mutated["calculation_run_id"] = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a02"
            self.assertNotEqual(
                contract_sync.runtime.calculate_digest(mutated),
                document["content_digest"],
            )

    def test_noncanonical_decimal_is_rejected(self) -> None:
        resolution = next(
            document
            for document in self.valid_documents
            if document["schema_version"] == "resolved-twin-architecture.v1"
        )
        mutated = copy.deepcopy(resolution)
        mutated["cost_summary"]["monthly_total"] = "7.60"
        contract_sync._redigest(mutated)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                mutated,
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_SCHEMA_INVALID")

    def test_catalog_mapping_and_resolution_cost_drift_fail_closed(self) -> None:
        provider = next(
            document
            for document in self.valid_documents
            if document.get("implementation_profile_id")
            == "provider-profile.aws.baseline"
        )
        provider_mutation = copy.deepcopy(provider)
        provider_mutation["component_mappings"][0][
            "deployment_component_candidates"
        ] = ["deployment.aws.missing"]
        contract_sync._redigest(provider_mutation)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                provider_mutation,
                bundle_root=contract_sync.SOURCE_V1,
                linked_documents=self.valid_documents,
            )
        self.assertEqual(raised.exception.code, "ARCH_COMPONENT_UNAVAILABLE")

        resolution = next(
            document
            for document in self.valid_documents
            if document["schema_version"] == "resolved-twin-architecture.v1"
        )
        resolution_mutation = copy.deepcopy(resolution)
        resolution_mutation["cost_summary"]["monthly_total"] = "8"
        contract_sync._redigest(resolution_mutation)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                resolution_mutation,
                bundle_root=contract_sync.SOURCE_V1,
                linked_documents=self.valid_documents,
            )
        self.assertEqual(raised.exception.code, "ARCH_SCHEMA_INVALID")

    def test_extension_and_reference_sets_fail_closed(self) -> None:
        catalog_mutation = copy.deepcopy(self.catalog)
        catalog_mutation["components"][0]["extension_slot_refs"] = [
            {"id": "slot.unknown", "version": "1"}
        ]
        contract_sync._redigest(catalog_mutation)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                catalog_mutation,
                bundle_root=contract_sync.SOURCE_V1,
                linked_documents=self.valid_documents,
            )
        self.assertEqual(raised.exception.code, "ARCH_REFERENCE_UNRESOLVED")

        resolution = next(
            document
            for document in self.valid_documents
            if document["schema_version"] == "resolved-twin-architecture.v1"
        )
        binding_mutation = copy.deepcopy(resolution)
        binding_mutation["extension_bindings"] = [
            {
                "slot_id": "slot.unknown",
                "slot_version": "1",
                "artifact_id": "artifact.user.example",
                "artifact_digest": f"sha256:{'1' * 64}",
                "logical_component_id": "component.processing",
                "configuration_digest": f"sha256:{'2' * 64}",
                "validation_contract_version": "1",
            }
        ]
        binding_mutation["resolution_id"] = (
            contract_sync.runtime.calculate_resolution_id(binding_mutation)
        )
        contract_sync._redigest(binding_mutation)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                binding_mutation,
                bundle_root=contract_sync.SOURCE_V1,
                linked_documents=self.valid_documents,
            )
        self.assertEqual(raised.exception.code, "ARCH_EXTENSION_BINDING_INVALID")

        duplicate_ref = copy.deepcopy(resolution)
        duplicate_ref["provider_profile_refs"].append(
            copy.deepcopy(duplicate_ref["provider_profile_refs"][0])
        )
        contract_sync._redigest(duplicate_ref)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                duplicate_ref,
                bundle_root=contract_sync.SOURCE_V1,
                linked_documents=self.valid_documents,
            )
        self.assertEqual(raised.exception.code, "ARCH_DUPLICATE_ID")

    def test_lifecycle_transitions_are_monotonic(self) -> None:
        deprecated = copy.deepcopy(self.profile)
        deprecated["lifecycle_status"] = "deprecated"
        contract_sync.runtime.validate_lifecycle_transition(self.profile, deprecated)
        retired = copy.deepcopy(deprecated)
        retired["lifecycle_status"] = "retired"
        contract_sync.runtime.validate_lifecycle_transition(deprecated, retired)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_lifecycle_transition(retired, self.profile)
        self.assertEqual(raised.exception.code, "ARCH_VERSION_UNSUPPORTED")

    def test_credential_shaped_value_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.profile)
        mutated["description"] = (
            "forbidden -----BEGIN PRIVATE KEY----- embedded credential"
        )
        contract_sync._redigest(mutated)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                mutated,
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_SECRET_FIELD_FORBIDDEN")

    def test_validation_observability_is_bounded_and_payload_free(self) -> None:
        class CapturingLogger:
            def __init__(self) -> None:
                self.records = []

            def info(self, message, *, extra):
                self.records.append((message, extra))

        logger = CapturingLogger()
        contract_sync.runtime.validate_document(
            self.profile,
            bundle_root=contract_sync.SOURCE_V1,
            logger=logger,
            correlation_id="corr-phase-8-2",
        )
        self.assertEqual(len(logger.records), 1)
        message, extra = logger.records[0]
        self.assertEqual(message, "architecture_contract_validation")
        record = extra["architecture_contract"]
        self.assertEqual(record["result"], "accepted")
        self.assertEqual(record["contract_id"], "five-layer-baseline")
        self.assertEqual(record["correlation_id"], "corr-phase-8-2")
        serialized = json.dumps(record, sort_keys=True)
        self.assertNotIn(self.profile["description"], serialized)
        self.assertNotIn("responsibilities", serialized)

        rejected = copy.deepcopy(self.profile)
        rejected["profile_id"] = "UNSAFE-LOG-VALUE"
        contract_sync._redigest(rejected)
        with self.assertRaises(contract_sync.runtime.ContractError):
            contract_sync.runtime.validate_document(
                rejected,
                bundle_root=contract_sync.SOURCE_V1,
                logger=logger,
            )
        rejected_record = logger.records[-1][1]["architecture_contract"]
        self.assertEqual(rejected_record["contract_id"], "invalid")
        self.assertNotIn("UNSAFE-LOG-VALUE", json.dumps(rejected_record))

    def test_schema_errors_do_not_echo_rejected_values(self) -> None:
        marker = "DO-NOT-ECHO-THIS-REJECTED-VALUE"
        mutated = copy.deepcopy(self.profile)
        mutated["display_name"] = marker * 10
        contract_sync._redigest(mutated)
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                mutated,
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_SCHEMA_INVALID")
        self.assertNotIn(marker, str(raised.exception))

    def test_non_json_input_fails_with_stable_contract_error(self) -> None:
        mutated = copy.deepcopy(self.profile)
        mutated["display_name"] = float("nan")
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_document(
                mutated,
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_SCHEMA_INVALID")

    def test_linked_bundle_rejects_duplicate_contract_identity(self) -> None:
        with self.assertRaises(contract_sync.runtime.ContractError) as raised:
            contract_sync.runtime.validate_bundle(
                [*self.valid_documents, copy.deepcopy(self.profile)],
                bundle_root=contract_sync.SOURCE_V1,
            )
        self.assertEqual(raised.exception.code, "ARCH_DUPLICATE_ID")

    def test_immutable_reader_rejects_mutation(self) -> None:
        validated = contract_sync.runtime.validate_document(
            self.profile,
            bundle_root=contract_sync.SOURCE_V1,
        )
        with self.assertRaises(TypeError):
            validated.document["profile_id"] = "changed"
        mutable_copy = validated.as_dict()
        mutable_copy["profile_id"] = "changed"
        self.assertEqual(validated.stable_id, "five-layer-baseline")

    def test_resolved_deployment_v1_remains_baseline_only(self) -> None:
        schema = contract_sync._read_json(
            ROOT
            / "contracts"
            / "resolved-deployment-specification"
            / "v1"
            / "schema.json"
        )
        profile_schema = schema["properties"]["architecture_profile"]
        serialized = json.dumps(profile_schema, sort_keys=True)
        self.assertIn("five-layer-baseline", serialized)
        self.assertNotIn("eventing", serialized.lower())
        resolution = next(
            document
            for document in self.valid_documents
            if document["schema_version"] == "resolved-twin-architecture.v1"
        )
        self.assertEqual(
            resolution["deployment_specification_ref"]["schema_version"],
            "resolved-deployment-specification.v1",
        )

    def test_profile_is_provider_and_terraform_neutral(self) -> None:
        serialized = contract_sync.runtime.canonical_json(self.profile).lower()
        for forbidden in (
            "terraform",
            "resource_address",
            "endpoint",
            "arn:",
            "provider_sdk",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_catalog_contains_only_declarative_terraform_bindings(self) -> None:
        for component in self.catalog["components"]:
            binding = component["terraform_binding"]
            self.assertNotIn("runtime_resource_name", binding)
            self.assertTrue(binding["resource_addresses"])
            self.assertTrue(binding["outputs"])

    def test_remote_schema_references_are_forbidden(self) -> None:
        for filename in contract_sync.SCHEMA_FILES:
            schema = contract_sync._read_json(contract_sync.SOURCE_V1 / filename)

            def walk(value: object) -> None:
                if isinstance(value, dict):
                    reference = value.get("$ref")
                    if isinstance(reference, str):
                        self.assertTrue(
                            reference.startswith("#/")
                            or reference.startswith("semantic-registry.schema.json#/")
                        )
                    for nested in value.values():
                        walk(nested)
                elif isinstance(value, list):
                    for nested in value:
                        walk(nested)

            walk(schema)

    def test_fresh_copy_has_deterministic_tree_digest(self) -> None:
        expected = contract_sync.contract_tree_digest()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / contract_sync.CONTRACT_NAME
            shutil.copytree(contract_sync.SOURCE_ROOT, target)
            digest = hashlib.sha256()
            for path in sorted(
                item
                for item in target.rglob("*")
                if item.is_file()
                and item.name != ".contract-sha256"
                and "__pycache__" not in item.parts
            ):
                digest.update(path.relative_to(target).as_posix().encode("utf-8"))
                digest.update(b"\0")
                digest.update(path.read_bytes())
                digest.update(b"\0")
            self.assertEqual(f"sha256:{digest.hexdigest()}", expected)


if __name__ == "__main__":
    unittest.main()
