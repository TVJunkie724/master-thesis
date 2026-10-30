# Minimal L5 visualization — pre-implementation review

Current restoration (2026-10-25): AWS and Azure return to managed Grafana,
reusing the existing provider provisioning and Raw/Hourly dashboard code.
The normal Terraform path, access read model and cost catalog have been
updated; live verification is pending. AWS retains an IAM-protected L3 reader;
Azure retains its function-scoped reader credential in the datasource secret.
The UI opens the provider dashboard with the existing operator identity.
GCP L4/L5 remain excluded, and the research questions remain unchanged.
Previous HTML/SVG passes prove only that historical implementation, not Grafana.
See [the bounded restoration plan](../../plans/2026-10-25_restore_managed_grafana.md).

Current AWS authentication amendment (2026-10-25): the managed Infinity 4.1.3
backend query failed with an unavailable default SDK credential chain. The user
approved one deployment-owned, URL-only IAM reader identity instead of copying
administrator credentials or exposing the reader. Its access key is generated
in SDK memory, supplied through Grafana secureJsonData and revoked on failed
postapply or user Destroy. It is a static credential for the deployment lifetime,
not an expiring STS session; no rotation service is added to this PoC. Terraform
owns the user/policy and deletes non-Terraform keys with that dedicated user.
The secret is not a Terraform output/state value or a Flutter credential.
This supersedes the runtime-role prerequisite for AWS below; the original failed
role-authentication observation remains unchanged. Local signed fixture queries
pass, but a fresh managed-cloud simulator/browser run is still required.

Historical decision (2026-10-05): the user approved a minimal AWS/Azure
server-rendered graphical consumer instead of this Managed Grafana proposal.
The approved fixed L3→L5 experiment, claim boundaries and results are recorded
in [the minimal L5 evidence plan](../../plans/2026-10-05_minimal_l5_evidence.md).
The pricing proposal and execution block below are historical, not the active
experiment. GCP exclusion, unchanged RQs and the historical FiveLayer reference
still apply. A stored fixture proof must not be described as simulator→L5.

Status: reviewed offline/public read-only on 2026-09-07; **blocked for execution**.
This is a resource proposal and feasibility result, not an executable Terraform
plan, spending approval, or live readiness evidence. No cloud resources were
created and no account credentials were read during this review.

Scope update (2026-09-16): the GCP L4/L5 replacement proposal below is
superseded. No GCP visualization VM or custom Twin replacement will be built
for this PoC. Readers are now owned by L3; graphical L5 remains pending for
AWS/Azure. See [the separation plan](../../plans/2026-09-16_poc_l3_read_access_separation.md).

## Smallest useful result

One provider-hosted dashboard, one device and metric, and two panels: recent
raw telemetry and hourly rollups. Reuse the existing bounded reader contract
and dashboard definitions. Provision the datasource and dashboard
programmatically. Show actual simulator data, not only a successful HTTP
response. No Flutter chart client, dashboard editor integration, alerts,
monitoring platform, HA, credential-rotation UI, or additional baseline.

The current JSON-only implementation proves authenticated readback, **not
graphical visualization equivalence** to the original Five-layer responsibility.
The original model remains an unchanged offline historical reference. Even a
working chart would not make full architecture cost differences attributable
solely to Eventing.

## Proposed resource delta per scenario

These are intended resources beyond the current reader, not verified Terraform
resource counts. Existing L1–L4 and Event Layer resources are unchanged.

| Provider | Proposed L5 resources | Reuse and remaining integration |
|---|---|---|
| AWS, `eu-central-1` | One Managed Grafana workspace, workspace IAM role/policy, existing Identity Center user association, one temporary provisioning service account/token; one datasource and dashboard | Reuse `layer_5_grafana.py` dashboard shape. Its old shared-header reader authentication cannot call today's `AWS_IAM` Lambda URL. A compatible, pinned SigV4 datasource using a runtime role must be proved before restoration; do not make the reader public or copy administrator keys into Grafana. |
| Azure, `westeurope` | One Managed Grafana Standard X1 instance, managed identity, scoped deployer/user role assignments, bounded provisioning token; one datasource and dashboard | Reuse `layer_5_grafana.py` and the function-key bootstrap. Verify the selected managed version/plugin combination. No zone redundancy or Enterprise plugin license. |
| GCP, `europe-west1` | One `e2-medium` VM, one 20-GiB boot disk with auto-delete, one ephemeral external IPv4, one VM service account with reader invocation permission, narrowly scoped SSH firewall rule; one Grafana container, datasource and dashboard | Reuse the scenario network and old dashboard template, not the GKE Grafana workload. Bind Grafana to VM loopback and use an operator SSH tunnel. Do not expose port 3000 publicly. The old startup script uses a removed shared reader key; audience-bound Cloud Run identity-token acquisition/renewal must be proved first. |

For GCP, the SSH source address and exact zone must be resolved before a real
plan; never default to world-open ingress. VM image, container and plugin
digests must be frozen and smoke-tested locally. No new GKE cluster, load
balancer, NAT gateway, domain or public certificate is proposed for L5. The
existing GCP L1 cluster and separate L4 IAP decision are unaffected.

## Cost findings and stop condition

All figures below are USD public list prices or explicitly labelled arithmetic,
not invoices or spending caps. Trials and credits are **not assumed**. Account
trial eligibility was not established; workspace absence would not prove it.
No trial was activated and no paid billing-query API was called.

- **AWS:** minimum USD 9 per workspace/month. An active Admin/Editor service
  account also costs USD 9; a human Admin/Editor costs USD 9, a Viewer USD 5.
  Existing automation plus one human Admin therefore implies USD 18 per
  workspace in one billing month, excluding other services. Deleting the
  provisioning identity does not undo its billable activity.
  [AWS pricing](https://aws.amazon.com/grafana/pricing/).
- The frozen matrix places L5 on AWS in `small-local-aws`,
  `small-focus-azure-to-aws`, and `small-focus-aws-to-gcp`: three separately
  created workspaces. Thus the unconditional no-trial workspace floor is
  **USD 27**, or **USD 54** for the stated automation-plus-human-Admin example.
  Retries creating new workspaces and crossing billing months can add charges.
  The floor alone exceeds the existing USD 25 portfolio ceiling; each AWS
  workspace exceeds the USD 3 per-scenario ceiling. This is a definite stop,
  not a reason to silently raise caps or retain workspaces across Destroy.
- **Azure:** the public Retail Prices API returned West Europe Standard Node
  USD 0.0445/hour and Standard User USD 6/month. Standard X1 consumes two
  Standard Units, giving USD 0.089/hour if the Node meter is the applicable SU
  meter; confirm that mapping in the final resource quote. Active identities
  include API/service accounts. The FAQ describes first/last-month user
  proration by days, not `monthly_price / 730` for a short run. An illustrative
  two-identity, one-day September allocation is USD 0.40 plus instance time;
  it is not a verified account-specific cap. Reuse of a human across instances
  can avoid duplicate user fees, but newly generated service accounts differ.
  [Pricing](https://azure.microsoft.com/en-us/pricing/details/managed-grafana/),
  [billing FAQ](https://learn.microsoft.com/en-us/azure/managed-grafana/faq).
- Azure API query: `https://prices.azure.com/api/retail/prices`, currency USD,
  filter `contains(productName, 'Grafana') and armRegionName eq 'westeurope'`.
  Returned meter IDs: Node `0ac71480-39ee-5538-b344-4d7e3fb8932d`, User
  `6fd60a85-00b9-5645-97d8-0282bcf2f617`; no further result page.
- **GCP:** charge VM runtime + provisioned disk duration + IPv4 duration +
  transfer, image preparation/storage and reader requests. Compute has a
  one-minute minimum followed by per-second billing; an in-use standard-VM
  external IPv4 is USD 0.005/hour. The repository's legacy Grafana VM/disk
  rates are marked `fallback_static`; they are not a verified quote for this
  new VM/disk selection. A numerical all-in cap therefore remains unresolved.
  [Compute billing](https://cloud.google.com/products/compute/pricing),
  [IPv4 pricing](https://cloud.google.com/vpc/pricing).

The existing USD 20 nine-scenario proposal prices the **JSON-only graph**. It
must not be relabelled as covering this visualization proposal. Candidate,
pricing and image digests remain unchanged, and matrix execution stays disabled.

## Verification and cleanup after a later approval

Keep the [live protocol](live-evaluation-protocol.md) as the sole checklist:
L1–L3/Event Layer, L4, L5, then simulator/roundtrip checks within the recorded
attempt. This proposal does not introduce layer-targeted Terraform Apply.
For L5, verify authenticated access, both data series against reader results,
and an actual rendered simulator datapoint; empty panels are not success.
Record deployment/configuration/verification time and L5 costs in the existing
attempt record, not a new reporting system.

On failure or the existing minute-50 trigger, stop functional work and attempt
Destroy immediately; minute 60 remains the cleanup target, not a hard billing
cutoff. Reconcile workspace/VM deletion, disk and IP release, scenario-owned
IAM bindings, tokens, image artifacts and network rules. Do not delete shared
administrator identities or pre-existing networks. Preserve delayed license
charges in cost reconciliation even after inventory is clean.

## Decision required

Restoring managed AWS L5 for every assigned scenario is not feasible under the
unchanged technical caps without verified applicable credits. Stop before
runtime restoration, new pricing snapshots, or cloud mutation. A cheaper
hosting choice (for example self-hosted AWS Grafana) changes the proposed
provider service mapping and requires an explicit decision plus its own bounded
cost/authentication check. Do not silently substitute it or claim that this
review has solved L5.
