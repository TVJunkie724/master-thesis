# Minimal live L5 evidence — AWS and Azure

Status: approved, implementation and verification in progress (2026-10-05).

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
