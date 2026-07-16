# Extension Points

## Add A Flutter Feature

1. define/extend the `ManagementApi` contract and typed models;
2. implement network and demo adapters;
3. choose Riverpod for composition/simple global state or BLoC for a complex workflow;
4. add route/screen/task and responsive widget tests;
5. pass the frontend architecture script, analysis, tests, and builds.

## Add A Management Workflow

1. add Pydantic request/response contracts;
2. implement application service and repository/client dependencies;
3. keep the route as HTTP mapping;
4. add an idempotent migration for persistence changes;
5. test ownership, lifecycle, errors, redaction, and downstream failures;
6. expose it through Flutter/demo only after the public contract is stable.

## Add Pricing Or An Optimization Objective

For a field: intent, provider mapping, source classification, normalizer, provider
pricing contract, formula binding, evidence fixtures, accepted/rejected candidates, and
tier/unit tests must advance together.

For an objective: metric provider, intent group, calculation model, workload/provider
contracts, formula set, scoring strategy, result schema, enabled profile, traceability,
and broad verification are all required. A disabled declaration alone is not a feature.

## Add Deployer Provider Behavior

Implement the provider protocol/registry entry, package builder, capability declaration,
preflight permissions, cleanup/destroy behavior, outputs, status/verification probes,
and mocked tests. Add workspace synchronization only for state required by later
operations and use the explicit allowlist.

## Add A User Function

Register layer/role metadata, preserve provider entrypoint/package conventions, validate
source/dependencies, generate deterministic archives, and test both local validation and
provider package structure. Do not add one-off upload endpoints for a single function.

## Add Documentation

Place current material under `docs-site/docs`; update `mkdocs.yml`; keep diagrams in
context; use an issue for active future work; and update the provenance appendix if an
old HTML/Markdown source is replaced.
