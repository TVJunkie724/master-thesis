# Phase 7b: Unsupported Error-Handling Topology

**Issue:** [#135](https://github.com/TVJunkie724/master-thesis/issues/135)
**Status:** Done
**Blocked by:** #127

## Target

The executable `five-layer-baseline@1` contract must not claim provider
error-routing resources that the Deployer cannot create. The legacy
`integrateErrorHandling` field remains readable for compatibility, but only
`false` or omission is executable. `true` fails with the stable code
`UNSUPPORTED_ERROR_HANDLING_TOPOLOGY`.

This policy does not disable event checking, notification workflows, device
feedback, or user-authored event actions. Those are separate supported
features.

## Boundary Contract

| Boundary | Required behavior |
| --- | --- |
| Optimizer HTTP schema | Reject `true` with a machine-readable validation type before catalog resolution |
| Optimizer calculation engine | Reject `true` when called directly, before provider calculations |
| Management write schemas | Reuse one validator for calculate, config, and run creation endpoints |
| Management run persistence | Validation occurs before catalog lookup, downstream calls, or database writes |
| Management deployment package | Reject historical or externally introduced `true` before ZIP creation |
| Deployer config validation | Reject flat and canonical nested optimization documents |
| Deployer project loading | Reject before package building, tfvars generation, or Terraform |
| Flutter | Keep the control disabled, describe the baseline limitation, and never ship demo data with `true` |

## Implementation

1. Add one small topology-policy module per Python service boundary. Each
   exposes the same field name, error code, public message, and strict
   validation rule.
2. Bind the policy to both Pydantic request models. Use a Pydantic custom error
   so FastAPI's `422` detail contains the domain error code as its validation
   type.
3. Guard the Optimizer engine as defense in depth for direct callers.
4. Guard Management deployment-package projection so legacy persisted data
   cannot be converted into a deployable package.
5. Guard Deployer normalization and file validation. Do not convert `true` to
   `false`, and do not let the tolerant optional-file loader swallow this
   policy violation.
6. Keep Flutter deserialization compatible with historical results. The
   disabled control must communicate that the baseline does not deploy the
   topology; demo and test fixtures use `false`.
7. Regenerate semantic OpenAPI snapshots after the request contracts change.

## Error Semantics

```text
error code: UNSUPPORTED_ERROR_HANDLING_TOPOLOGY
field: integrateErrorHandling
HTTP request validation: 422
project/deployment preflight: fail before side effects
```

No layer silently removes or rewrites the requested capability. Error text
must not contain credentials, provider payloads, or project file contents.

## Tests and Gates

- Optimizer model and HTTP tests for `true`, `false`, and omission.
- Optimizer direct-engine test proving rejection occurs before provider work.
- Management parameterized tests across all four canonical write routes.
- Management run-creation and deployment-package tests proving zero downstream
  or persistence side effects.
- Deployer flat/nested config validation, directory/ZIP preflight, loader, and
  false/omitted compatibility tests.
- Flutter model, disabled-control, and demo-fixture tests.
- Semantic OpenAPI snapshot synchronization.
- Full safe suites, changed-file static analysis, Bandit, and strict docs build.

## Verification Evidence

- Optimizer: 808 tests passed.
- Management API: 873 tests passed.
- Deployer: 1,638 tests passed and one live-E2E test was skipped.
- Flutter: 675 tests, static analysis, web build, and macOS build passed.
- Focused negative tests reject the topology before provider calculation,
  persistence, credential resolution, package creation, tfvars generation, or
  Terraform execution.
- OpenAPI export, Ruff, Bandit, compileall, secret scanning, strict MkDocs,
  and repository diff checks passed.
- No live or billable cloud apply was executed.

## Definition of Done

- [x] `true` cannot enter calculation, persistence, package creation, or Terraform.
- [x] Every canonical request boundary exposes the stable error code.
- [x] `false` and omitted legacy payloads remain executable.
- [x] Historical data containing the field remains readable.
- [x] Event checking, workflows, feedback, and event actions remain unchanged.
- [x] Flutter and demo mode do not imply that the topology is supported.
- [x] Documentation and OpenAPI snapshots match the executable contract.
- [x] #135 is closed with commit and verification evidence.
