# API and Contracts

## Direction

```text
Flutter typed models
       |
       v
Management Pydantic API
       |             |
       v             v
Optimizer client   Deployer client
```

Flutter must not mirror internal provider payloads or call internal services.
Management adapts them into stable owner-scoped, redacted contracts.

## Canonical evidence chain

```text
Twin + workload + fixed architecture pin
  -> calculationRunId + exact frozen pricing refs
  -> cost result + trace + RTA v2 + RDS v2
  -> Management cross-link and digest validation
  -> Manifest v4 package
  -> graph readiness + operation
  -> verification + cleanup evidence
```

The public calculation request cannot author the server-owned run ID, pricing
references, architecture pin, extension bindings, resolved assignments, or
Terraform values. Account-specific pricing contexts are not part of the
contract.

## Change rules

- update canonical source, generated copies, fixtures, and every affected
  consumer together;
- use explicit schema versions and canonical SHA-256 digests for durable
  evidence;
- reject unknown fields and secret-like content;
- add positive and fail-closed negative tests;
- never synthesize missing provider values from defaults downstream;
- keep offline and live evidence labels distinct.

Representative synchronization commands include:

```bash
python scripts/sync_six_layer_contracts.py --sync --check
python scripts/sync_six_layer_workload_contract.py --sync --check
python scripts/sync_user_function_extension_contracts.py --sync --check
python scripts/sync_deployment_access_contracts.py --sync --check
```

OpenAPI snapshots under `docs/contracts/openapi/` are regenerated from the
current applications and checked for removed public surfaces.
