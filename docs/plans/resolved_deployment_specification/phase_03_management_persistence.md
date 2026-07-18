# Phase 3: Management Persistence and Manifest Binding

**Issue:** [#130](https://github.com/TVJunkie724/master-thesis/issues/130)  
**Status:** Implemented and verified

**Blocked by:** #127, #129

## Target

The Management API is the trust and ownership boundary. It preallocates the run
ID, validates the returned specification, recomputes its digest, persists it
atomically, and embeds the same immutable object in DeploymentManifest v2.

## Data Model and Migration

Add non-secret columns to `cost_calculation_runs`:

- `deployment_specification_json` nullable text for legacy compatibility;
- `deployment_specification_digest` nullable indexed string;
- `deployment_specification_version` nullable string;
- `deployment_compatibility_status` non-null string with
  `legacy_not_deployable` as migration default.

The migration is idempotent and registered in the existing migration runner.
New successful runs must use `ready`; failed validation must roll back the whole
run and projection update.

## Service Boundaries

1. Preallocate `CostCalculationRun.id` before calling the Optimizer.
2. Pass it as `calculationRunId`.
3. Validate structure, semantic registry values, run identity, provider path,
   pricing catalog references, and digest.
4. Persist canonical JSON, not the untrusted input byte representation.
5. Keep the specification immutable after creation.
6. Require `ready` plus current pricing/account context when selecting a run.
7. Expose a typed read-only projection in run detail and selection responses.
8. Build DeploymentManifest v2 with:
   - `calculation_run_id`;
   - `resolved_deployment_specification`;
   - `resolved_deployment_specification_digest`.
9. Do not duplicate the specification into mutable twin configuration columns.

## Required File Boundaries

| Area | Files |
| --- | --- |
| ORM | `src/models/cost_calculation.py` |
| Migration | new migration plus `migrations/runner.py` and migration tests |
| Typed API | `src/schemas/cost_calculation.py` |
| Trust boundary | `src/services/cost_calculation_run_service.py` and a focused specification validator |
| Optimizer request | `src/clients/optimizer_client.py`, calculation schemas |
| Selection errors | `src/services/errors.py`, route error mapping |
| Manifest | `src/services/deployment_service.py` |
| API | `src/api/routes/optimizer_runs.py`, generated OpenAPI fixture |

Routes remain thin. ORM writes, canonicalization, and selection policy stay in
the service/repository boundary.

## Compatibility

Legacy runs remain listable and inspectable. Selection returns a typed conflict
requiring recalculation. No service may synthesize a specification from
`cheapest_l1` through `cheapest_l5`.

## Security and Errors

- reject all secret-like keys recursively;
- cap specification/component/dimension sizes;
- never log full optimizer or manifest payloads;
- use stable domain codes for missing, invalid, stale, and digest-mismatched
  specifications;
- preserve transaction rollback on any contract failure.

## Tests

- migration on empty and populated databases;
- successful atomic persistence;
- optimizer run-ID mismatch;
- digest and canonicalization mismatch;
- secret-field rejection;
- unknown component/value rejection;
- rollback after result-item creation failure;
- legacy run read versus select behavior;
- concurrent selection and immutability;
- manifest v2 exact-object/digest binding;
- API/OpenAPI response contracts.

## Definition of Done

- [x] New runs persist an immutable validated specification and digest.
- [x] Legacy runs are readable and explicitly not deployable.
- [x] Selection and manifest generation reject all invalid compatibility states.
- [x] Manifest v2 carries the exact canonical object and digest.
- [x] Migration, rollback, concurrency, API, Ruff, Bandit, and full safe tests pass.
- [x] #130 is closed with commit and verification evidence.
