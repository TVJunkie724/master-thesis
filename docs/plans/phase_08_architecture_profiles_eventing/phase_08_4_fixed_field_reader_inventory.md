---
title: "Phase 8.4 Fixed-Field Compatibility Inventory"
description: "Tracked owners and removal phases for the remaining cheapest-layer, provider-key, and fixed-slot consumers."
tags: [architecture, migration, compatibility, management-api, flutter]
lastUpdated: "2026-07-19"
version: "1.0"
---

# Phase 8.4 Fixed-Field Compatibility Inventory

This inventory is the transition contract for the old seven-slot
`cheapest_l*`, `layer_*_provider`, and Flutter fixed-slot projections. For an
architecture-ready run, the executable source of truth is the immutable
`ResolvedTwinArchitecture`; fixed fields are derived only for
`five-layer-baseline@1`. The live calculation path remains legacy until Phase
8.6 activates the dark Phase 8.5 architecture output together with the typed
Deployer graph compiler.

The executable drift gate remains
`scripts/architecture_inventory/extractors.py`. It currently covers 100 exact
anchors across 20 source files and fails when an undeclared consumer appears or
a declared consumer moves.

## Management `cheapest_l*` Consumers

| Consumer | Transitional purpose | Owning phase |
|---|---|---|
| `src/models/optimizer_config.py` | Non-destructive historical columns | Retained history; never an executable SSOT |
| `migrations/add_resolved_twin_architecture.py` | Conservative reconstruction evidence; mismatches remain legacy | Phase 8.4 only |
| `src/services/resolved_architecture_service.py` | Server-owned baseline projection and round-trip check | Phase 8.4 owner; retained compatibility projection |
| `src/services/cost_calculation_run_service.py` | Legacy result write and run-selection projection | Phase 8.5 integrates dark; Phase 8.6 removes |
| `src/services/credential_resolution_service.py` | Provider requirement projection | Phase 8.6 |
| `src/services/deployment_operation_service.py` | Operation provider projection | Phase 8.6 |
| `src/services/deployment_read_service.py` | Deployment read projection | Phase 8.6 |
| `src/services/deployment_service.py` | Package and provider-key projection | Phase 8.6 |
| `src/services/optimizer_configuration_service.py` | Legacy calculation readiness check | Phase 8.6 |
| `src/services/project_zip_extraction_service.py` | Legacy project import projection | Phase 8.6 |
| `src/services/simulator_service.py` | L1 simulator provider projection | Phase 8.6 |
| `src/services/test_deployment_service.py` | Offline deployment-test projection | Phase 8.6 |
| `src/services/verification_service.py` | Verification provider projection | Phase 8.6 |
| `src/api/routes/twin_operations.py` | Public compatibility read model | Phase 8.7 |
| `src/services/optimizer_config_projection.py` | Flutter-facing compatibility read model | Phase 8.7 |

All paths in this table are relative to `twin2multicloud_backend/`.

## Provider-Key And Flutter Consumers

Phase 8.6 owns the remaining Management `layer_*_provider` readers in
`deployment_read_service.py`, `deployment_service.py`, and
`test_deployment_service.py`.

Phase 8.7 owns the remaining Flutter provider-key and fixed-slot presentation
in:

- `lib/features/configuration_workspace/presentation/deployment/deployment_config_section.dart`;
- `lib/widgets/file_inputs/config_visualization_block.dart`;
- `lib/models/architecture_path.dart`;
- `lib/widgets/architecture/architecture_service_map.dart`;
- `lib/widgets/architecture_graph.dart`;
- `lib/features/configuration_workspace/presentation/deployment/deployment_layer_overview.dart`.

## Removal Gate

A consumer leaves this inventory only when its owning phase:

1. reads the selected immutable architecture or a typed projection derived from
   it;
2. has a fail-closed test proving fixed-field mutation cannot change executable
   behavior;
3. updates the allowlist and regenerates the Phase 8 architecture inventory;
4. keeps historical fixed columns readable without reconstructing missing
   architecture evidence.

After Phase 8.7, only the historical columns and the server-owned baseline
round-trip projection may remain.
