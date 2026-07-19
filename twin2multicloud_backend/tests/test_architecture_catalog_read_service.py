"""Focused tests for the Phase 8.3 internal Management catalog projection."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.services.architecture_catalog_read_service import (
    ArchitectureCatalogReadService,
)


def test_catalog_summary_is_typed_complete_and_dark():
    summary = ArchitectureCatalogReadService.read_summary()

    assert summary.profile_id == "five-layer-baseline"
    assert summary.responsibility_count == 5
    assert summary.logical_component_count == 7
    assert summary.logical_edge_count == 6
    assert summary.optimization_slot_count == 7
    assert summary.functional_completeness_rule_count == 12
    assert summary.extension_slot_ids == ("processor.telemetry",)
    assert summary.deployment_component_count == 22
    assert summary.edge_implementation_count == 33
    assert summary.package_artifact_count == 43
    assert summary.runtime_activation == "dark-read-only"
    assert [provider.provider for provider in summary.providers] == [
        "aws",
        "azure",
        "gcp",
    ]
    assert all(provider.supported is False for provider in summary.providers)


def test_catalog_summary_is_frozen():
    summary = ArchitectureCatalogReadService.read_summary()
    with pytest.raises(ValidationError):
        summary.runtime_activation = "active"
