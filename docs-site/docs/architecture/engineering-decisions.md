# Engineering Decisions

The durable decision log lives at
`docs/development_and_decision_log.md` in the repository. The key implemented
outcomes are summarized here.

| Decision | Implemented consequence |
|---|---|
| one Six-layer architecture | read-only canonical contract; no profile catalog, selection, inheritance, or registration |
| cost-only optimization | one small scoring strategy and full trace; no inactive objective registry |
| frozen prices | dated, cited, hashed snapshots; no refresh/review/admin workflow |
| resolved graph as source of truth | readiness, permissions, identities, packages, Terraform inputs, probes, and cleanup derive from one digest |
| pre-existing administrator credentials | multiple named encrypted deployment connections; no credential creation/rotation/revocation product |
| immutable deployed Twins | typed Duplicate/Export/Import rather than update/migration/rollback |
| durable Deploy/Destroy | idempotent commands, persisted progress, SSE replay, verification and cleanup evidence |
| access handoff | provider-accurate URL/identity information and telemetry proof; no embedded dashboard administration |
| profile-bound startup | one owner profile and static local bearer; no Google, Microsoft, or university-SAML application login |

Patterns are retained where they make a real seam testable. For example, the
cost scorer implements a strategy boundary, but only one runtime strategy is
registered. This demonstrates how the code can evolve without claiming a
generic optimization product.

AI assistance is documented as an engineering method, not scientific evidence.
Human review owns research decisions, provider authorization, result
interpretation, and claims about live behavior.
