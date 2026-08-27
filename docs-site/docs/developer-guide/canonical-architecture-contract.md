# Canonical Architecture Contract Development

The source bundle is under:

```text
contracts/architecture-profiles/v2/
contracts/architecture-profiles/definitions/
```

The `v2` path is a schema version, not a second architecture. The only
definition is `six-layer-eventing/1`.

## Change procedure

1. Change the canonical schema, semantic registry, fixed definition, provider
   mapping, component catalog, or deterministic fixture builder.
2. Keep the logical graph free of credentials, physical names, endpoints,
   provider SDK payloads, and arbitrary Terraform values.
3. Update cost, capability, deployment, readiness, verification, and cleanup
   bindings together when semantics change.
4. Add positive and negative contract/graph tests.
5. Refresh digests and generated copies.
6. Run focused cross-service gates, then relevant full offline suites.
7. Update current documentation and research traceability.

```bash
python scripts/refresh_six_layer_contract_digests.py
python scripts/sync_six_layer_contracts.py --sync --check
```

## Fixed-boundary rule

Do not add a public profile catalog, selection route, inheritance reference,
plugin loader, or graph editor. A hypothetical alternative architecture is
future research requiring an explicit scope decision and a new evaluation
design; it is not an extension point of the current PoC.

Provider components and directed edges remain developer-authored closed-world
definitions. Each must name exact capability, pricing/formula, package,
Terraform, permission, trust, observability, verification, and cleanup
evidence. Runtime code consumes injected graph bindings and does not reconstruct
resource identifiers from naming conventions.
