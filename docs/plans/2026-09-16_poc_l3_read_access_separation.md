# PoC: separate storage read access from visualization

Status: implementation plan; offline only. Research questions and the original
Five-layer baseline remain unchanged. No cloud execution, dashboard replacement,
general partial-deployment framework, or UI redesign is authorized by this plan.

## Bounded responsibility review

The review covers the active component selection, cost ownership, Terraform
resources and access handoff, not every implementation in the repository.

| Boundary | Finding | Action |
|---|---|---|
| L3 / L5 | Raw-history readers are owned, charged and exposed as visualization. Provider equality is consequently enforced in selection and validation. | Readers belong to L3 hot storage. A reader response is not visualization evidence. Separate ownership before admitting remote consumers. |
| L2 / Event Layer | Business actions/workflows and message delivery use shared runtime packages, but distinct functional and cost responsibilities. | Preserve; no rewrite based solely on shared packaging. |
| L3 storage tiers | Hot/cool/archive are deliberately co-located; movers belong to source storage. | Preserve this PoC restriction. Do not add storage migration. |
| L4 / L5 | The Twin explorer presents models/state/relationships, whereas the current L5 reader returns raw history/rollups. Both being readable does not make them the same function. | Keep AWS/Azure semantic Twin access. Exclude GCP Twin/visualization implementations from the final live scope; keep its storage reader. |
| Shared support | Logging/registry infrastructure is deduplicated; shared cost attribution is a convention, not an independent scientific layer. | Preserve and disclose; no new support platform. |
| Deployment / verification | One atomic Apply is followed by staged checks. | Do not claim that delayed checks avoid resource creation. A genuine core-only run remains separate preparation work. |

## Implementation sequence

1. Move reader selection, runtime lifecycle and cost ownership to L3. Reuse
   the same bounded API, authentication, resource identities and package; do
   not duplicate readers or copy administrator credentials into consumers.
2. Separate storage-read access from visualization readiness. Preserve explicit
   compatibility only where needed; do not turn an empty visualization slot
   into a successful or zero-cost graphical implementation.
3. Replace architectural provider equality with an explicit executable-reader
   integration boundary. Keep unimplemented cross-provider consumers blocked;
   removing a validator is not an integration implementation.
4. Reflect the GCP L4/L5 exclusion and revised coverage honestly in the active
   evaluation inputs. Old candidate/image/budget evidence cannot approve a new
   graph. No complete GCP-local result or fabricated replacement measurement.
5. Run offline regression checks, refresh generated contracts through existing
   scripts where affected, and commit coherent slices. No live E2E tests.

## Acceptance and non-goals

- A storage reader is selected by the storage provider, not the dashboard
  provider, and charged exactly once to storage.
- GCP storage remains conceptually supported independently of GCP L4/L5.
- An authenticated readback alone cannot establish L5 visualization success.
- Unsupported consumer/provider combinations fail explicitly before deployment.
- Five-layer baseline behavior and research-question wording do not change.
- No new VM, Grafana service, generic proxy, framework or product feature is
  introduced. AWS/Azure graphical implementation and its budget remain an
  explicit prerequisite, not a fabricated result of this refactor.
