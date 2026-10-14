"""Focused tests for the Phase 8.3 internal Management catalog projection."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.services.architecture_catalog_read_service import (
    ArchitectureCatalogReadService,
)


def test_catalog_summary_is_typed_complete_and_dark():
    summary = ArchitectureCatalogReadService.read_summary()

    assert summary.profile_id == "six-layer-eventing"
    assert summary.responsibility_count == 6
    assert summary.logical_component_count == 8
    assert summary.logical_edge_count == 9
    assert summary.optimization_slot_count == 8
    assert summary.functional_completeness_rule_count == 29
    assert summary.extension_slot_ids == ("processor.telemetry",)
    assert summary.deployment_component_count == 24
    assert summary.edge_implementation_count == 75
    assert summary.package_artifact_count == 7
    assert summary.runtime_activation == "active"
    assert [provider.provider for provider in summary.providers] == [
        "aws",
        "azure",
        "gcp",
    ]
    assert [provider.supported for provider in summary.providers] == [
        True,
        True,
        True,
    ]


def test_catalog_summary_is_frozen():
    summary = ArchitectureCatalogReadService.read_summary()
    with pytest.raises(ValidationError):
        summary.runtime_activation = "active"
