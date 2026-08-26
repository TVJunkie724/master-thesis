# Phase 8: standalone Six-layer PoC

Phase 8 now has one active cross-service architecture profile:
`six-layer-eventing@1`. It owns all six responsibilities, provider mappings,
workload resolution, costing, deployment specification, Terraform projection,
Management persistence, and Flutter presentation directly.

The intermediate runtime profile was removed. The original Five-layer model is
retained only as the Optimizer's historical baseline implementation and is not
published through shared contracts, Management, Deployer, Terraform, or Flutter.

Credential provisioning is also outside Phase 8. Operators provide a
preconfigured administrator credential for the supervised PoC; the retained
security boundary is documented in `docs/plans/2026-08-26_poc_credentials.md`.

## Active sources

- `docs/plans/2026-08-25_six_layer_only_architecture.md`
- `docs/plans/2026-08-26_poc_credentials.md`
- `docs/research/evidence/phase_08_eventing/`
- `docs/research/evidence/phase_08_service_bundles/`
- `contracts/architecture-profiles/definitions/six-layer-eventing-v1-manifest.json`
- `scripts/sync_six_layer_contracts.py`
- `scripts/verify_resolved_deployment_drift.py`

The remaining files in this directory cover the pre-change graph inventory,
the runtime Layer Access boundary, and the user-function extension contract.
They do not define additional deployable architecture profiles.
