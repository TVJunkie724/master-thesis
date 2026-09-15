# PoC: separate storage read access from visualization

Status: bounded separation implemented and verified offline. Research questions and the original
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

## Implementation and verification — 2026-09-16

- Reader selections, Terraform activation, SDK verification and cost ownership
  now follow L3 hot storage. Existing Terraform resource addresses are retained;
  canonical storage-access outputs coexist with explicitly deprecated L5 aliases.
- Candidate enumeration no longer co-locates L5 by architectural rule. The
  unimplemented remote-consumer edge still fails closed. Graphical L5 has no
  invented resource, charge or ready evidence; its missing implementation blocks
  publication even if a caller acknowledges every live-readiness gate.
- GCP's provider profile explicitly excludes L4/L5 while retaining lower-layer
  mappings. Eight revised complete-graph planning candidates materialize offline.
  GCP-only storage/core evaluation is not replaced by these mixed graphs.
- Storage-read-only replies cannot become ready graphical access evidence.
  Management can persist the offline graph but cannot select it for deployment.
- Unit tests for downstream package/path mechanics explicitly mock admission
  while retaining offline fixtures. Separate unmocked negative tests prove that
  execution admission rejects pending or relabelled L5. This is not a production
  partial-deployment feature or an E2E success claim.

Verification: 1,722 Deployer unit tests; five Terraform mock-plan tests;
33 Optimizer/contract tests; 20 Management contract/persistence tests; 68 root
scenario, budget, evidence and contract tests passed. The real offline
Optimizer-to-Management persistence check, contract synchronization, deterministic
service-bundle validation, changed-Python lint and strict documentation build
also passed. Terraform downloaded pinned provider packages for its mocked plans;
no cloud credentials, workload API, Apply or paid execution was used. The full
14-stage release gate and Flutter test suite were not rerun in this change.

Remaining work is deliberately outside this refactor: true core-only execution,
AWS/Azure graphical L5 and its cost decision, and authenticated remote L5-to-L3
consumption. Existing identity probe results remain historical, not new graph
authorization. RQ wording and the Five-layer baseline are unchanged.
