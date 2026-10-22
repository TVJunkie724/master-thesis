# Minimal live L5 evidence — AWS and Azure

Status: completed — both bounded live cuts and independent cleanup passed (2026-10-05).

The user approved a minimal provider-hosted graphical L5 proof. This replaces
the proposed Managed Grafana experiment for this evidence cut, not the historical
FiveLayer architecture or the research questions. GCP L4/L5 remain excluded.

## Fixed scope

- One independent L5 HTTP consumer per provider, hosted as Lambda/Functions.
- Two server-rendered SVG charts: raw history and hourly averages for one metric
  of one device, read through the existing authenticated L3 history contract.
- IAM-signed invocation on AWS; separate reader/visualization app keys on Azure.
  Azure's reader app has only its read route; its default function key is kept
  server-side. No account credentials, keys or signed URLs appear in the HTML.
- L5 has no direct storage permissions. AWS has a separate invocation-only role;
  Azure L5 has no Cosmos identity or data role. The existing readers stay in L3.
- Fixed create-only Terraform fixtures under `scripts/fixtures/l5`, not a new
  generic partial-deployment system. AWS: two on-demand DynamoDB tables, two
  Lambdas and IAM URLs, scoped roles/policies, two short-retention log groups.
  Azure: one resource group, serverless Cosmos account/database/container,
  private LRS package storage, two Flex plans/apps, reader/fixture data roles,
  the existing OneDeploy package modules. No Core, Event, L4, VM or Grafana.

## Acceptance and lifecycle

`scripts/run_l5_evaluation.py` first creates and validates an immutable fresh
plan against an exact address allowlist. Live execution additionally requires
an approved external allowance ledger and the operator's `--approve-live`
interlock. Functional deadlines: AWS 10 minutes, Azure 30 minutes; cleanup has
its own 30-minute deadline. These are failure limits, not predicted runtimes or
hard provider billing caps. No automatic repeated Apply is permitted.

Seed three raw points and three hourly records into actual L3 storage. L5 must
return two nonempty SVG charts with all six exact values and timestamps through
authenticated cloud HTTP. Both reader and visualization must reject requests
without authentication. Empty, invalid or truncated input fails closed.

Save the authenticated cloud-generated HTML, its SHA-256 and response metrics
privately. Render that byte-identical response for visual inspection and a
screenshot. This verifies the cloud-generated view; it does **not** establish
end-user SSO or interactive browser authentication. Never embed credentials into
the render artifact. Destroy immediately, then query provider inventory
independently of Terraform state. Preserve Plan/Apply, per-resource creation/
destruction, fixture, verification, Destroy and inventory durations and classify
reported billing separately from reservations.

## Thesis claims and exclusions

RQ1: reproducible deployment, packaging, authenticated read, timings and cleanup.
RQ2: the same two panels and bounded query contract on AWS/Azure. Explicitly a
small read-only visualization, not feature equivalence with Managed Grafana.
RQ3: on-demand consumption replaces fixed dashboard-service experiment floors;
no attribution of this mapping change to the Event Layer.

The seeded fixture proves **L3→L5**, not a new simulator→L5 or cross-cloud L5
roundtrip. Earlier Core, command and L4 observations remain separately scoped.
The full-profile graphical admission gate and management access integration are
not relaxed by this isolated experiment. No dashboard editor, alerts, Flutter
chart screen, product framework or unrelated UI work is introduced.

## Live observations

AWS attempt 03 used runtime/plan source `1d82debe` and passed: two nonempty
cloud-generated charts with the exact three raw and three hourly values and
timestamps; unauthenticated reader and L5 requests both returned 403. Deployment
took 40.512 s, verification 2.104 s, Destroy 15.376 s, total 63.792 s. All 15
resource creation/destruction timings are recorded. Independent SDK inventory
found zero tables, functions, roles and log groups for the unique run prefix.
The byte-identical cloud response was rendered locally after Destroy; browser
DOM and screenshot inspection confirmed two visible panels, three points each.
The original result remains immutable; rendering is a companion observation.

No failed cloud deployment preceded this success: preparations 01/02 stopped
after read-only planning because the execution container lacks Git. The runner
now accepts an explicit source revision. Azure's installed Resource SDK namespace
was corrected before any Azure Apply or allowance reservation. These are harness
preparation defects, not failed L5 cloud observations.

Azure attempt 03 passed on the same runtime/plan source, with runner SDK import
correction `f6b426bb`: two charts, three exact raw and three exact hourly values
and timestamps. Unauthenticated reader and L5 requests both returned 401.
Deployment took 561.910 s, fixture seeding 2.084 s, verification 7.190 s on the
first poll, Destroy 711.249 s and independent inventory 0.477 s; total
1291.029 s. All 20 Terraform creations and destructions have timing records.
The long Destroy was provider-side Cosmos/account and resource-group removal,
not repeated deployment or a failed message test. The independent ARM check
confirmed zero scoped resource groups after deletion. The preserved original
report has `functional_pass`, `cleanup_pass`, `inventory_pass` and `passed=true`.

Browser rendering confirmed both Azure panels with three points each while
Destroy was running. AWS and Azure generated byte-identical HTML from the
identical stored fixtures. Responses, their hashes, the immutable plans,
per-resource timings, inventories and companion render observations remain
private. Screenshots were inspected in the supervised browser session; no
browser SSO or publicly accessible dashboard was claimed. Both cloud cuts are
fully destroyed; the temporary local render server and agent-created tabs
were also closed.

The focused runtime, renderer, runner, package and response-header group passes
107 offline tests; Ruff and native Terraform validation pass. The L5 code is
packaged by the existing AWS/Azure deterministic ZIP builders; no new runtime
container image was published.

At 13:57 UTC, month-to-date billing reported AWS **0.1324709309 USD** (estimated,
account scope) and Azure **3.66834084223524 EUR** (subscription scope). The GCP
Console current-month view, verified against the project's active linked billing
account, reported **0.47 EUR net** (0.71 before 0.24 savings) for October 1–5.
The latter is billing-account scope, not a verified project filter. These lagged
totals include other attempts and cannot establish incremental L5 cost or be
summed across currencies.

## Subsequent diagnostic preparation — 2026-10-23

The historical Azure pass above used one always-ready HTTP instance in each
Function App. It is not proof of the normal profile's scale-to-zero behavior.
For a fresh L3/L5 diagnostic, the existing Azure fixture now omits both warm
instances; its create-only plan gate also checks the one-instance on-demand
ceiling and rejects unknown/warm capacity. Existing historical reports remain
unchanged. No IoT, Event, Twin service, image or dashboard platform is added.

The runner retains each HTTP status, client duration or exception class and
recognizes only the fixed `L5 data unavailable` body. Arbitrary bodies, keys,
URLs and exception text are not copied to diagnostic summaries. Azure's
authenticated requests permit 180 s within the existing 30-minute functional
deadline. This does not change the deployed handler's ten-second L3 timeout.
Anonymous rejection, exact SVG points and timestamps remain mandatory.
Direct raw/hourly L3 comparisons occur only after the L5 observation, including
ordinary failures; they cannot turn a failed L5 request into a pass. Terraform
cleanup now also checks managed entries nested in package modules before the
independent scoped ARM absence check. This preparation is not a new live pass
or a full application E2E result; execution needs its own reviewed saved plan
and sufficient authorized external allowance.
