# Phase 8 handoff

Use `six-layer-eventing@1` as the sole cross-service runtime profile. It is a
standalone contract, not an inherited extension. Five-layer v1 is limited to
the Optimizer's historical calculation path.

Before changing Phase 8:

1. Read `docs/plans/2026-08-26_thesis_poc_target_concept.md`.
2. Read `docs/plans/2026-08-26_thesis_poc_execution_plan.md` for dependencies.
3. Read `docs/plans/2026-08-26_poc_credentials.md` for the credential boundary.
4. Treat both Phase 8 evidence packages as generated and digest-bound.
5. Refresh contracts with `scripts/refresh_six_layer_contract_digests.py`, then
   run `scripts/sync_six_layer_contracts.py --sync --check`.
6. Run only offline gates by default. Live provider and E2E verification stays
   supervised and is not implied by an offline pass.

Do not reintroduce an intermediate runtime profile, generated deployment-admin
identities, generic permission packs, or permission-set version gates. Bounded,
confirmed provider preparation follows the resolved graph. Runtime identities
created inside a deployed Twin remain valid when required by a selected
provider service.
