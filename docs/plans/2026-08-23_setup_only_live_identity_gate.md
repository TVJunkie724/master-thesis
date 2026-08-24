# Setup-Only Live Gate Before Paid Cloud E2E

**Date:** 2026-08-23  
**Status:** In progress (G0, isolated credential-free G1, and version-aware
G4 validator logic implemented offline; G2-G5 not run)
**Parent issue:** [#107](https://github.com/TVJunkie724/master-thesis/issues/107)  
**Scope:** AWS, Azure, and GCP guided bootstrap, bounded deployment identities,
credential preflight, the fixed GCP Phase 8 API baseline, and cleanup only

## 1. Decision

Twin2MultiCloud must not move directly from offline tests to a paid
deploy/apply E2E. The first supervised provider validation is a separate
**setup-only live gate**:

```text
credential-free offline smoke
  -> read-only bootstrap-authority validation
  -> create one disposable bounded deployment identity
  -> persist it as a test CloudConnection
  -> validate the generated non-admin credential
  -> run provider/deployer preflight without Terraform apply
  -> delete the test CloudConnection and provider identity
  -> prove that no bootstrap secret was retained
  -> only then admit a paid Small single-cloud deploy/destroy smoke
```

The gate performs real IAM/directory mutations, so it is still opt-in and
supervised. On GCP it additionally batch-enables the separately pinned 19-API
Phase 8 baseline in an existing project and retains those APIs after identity
cleanup. It must not create IoT, compute, storage, broker, twin, visualization,
Kubernetes, or monitoring resources. This setup does not create the billable
workloads of the later architecture E2E, but it remains a security-sensitive
live test rather than an offline smoke.

## 2. Current Baseline And Gap

The repository currently proves the complete lifecycle only with the
`deterministic_fake` Management adapter. The production default is
`disabled`. The synchronized `supervised_live` mode is now recognized by the
canonical schema, Management, OpenAPI, and Flutter, but remains visibly blocked
by an unconfigured fail-closed adapter; a real provider credential cannot yet
cause the guided UI to create a provider identity.

The manual scripts under `bootstrap/<provider>/` are useful historical
fallbacks, but they are not sufficient as the new live gate:

- they still emit `thesis-demo-v1`, while Phase 8 requires immutable
  `thesis-demo-v2` deployment packs;
- they have no complete create/verify/cleanup test transaction;
- the Azure script assigns broad `Contributor` and
  `User Access Administrator` roles instead of the reviewed v2 role contract;
- the historical GCP script enables an unversioned API set without pinning it
  to the reviewed Phase 8 baseline or recording it independently from identity
  cleanup;
- they do not exercise the guided Management API, encrypted CloudConnection,
  Flutter resume state, or request-only bootstrap-secret boundary;
- generated secret JSON can be written to stdout unless an output file is
  selected.

The next implementation slice must therefore add a reviewed live adapter and
a setup-only runner rather than relabel the existing deployment E2E tests.

### 2.1 Contract Findings To Resolve Before Live Execution

- `CloudBootstrapGuide.execution_mode` and Management settings now share the
  exact `disabled`, `deterministic_fake`, and `supervised_live` vocabulary
  across canonical schemas, generated copies, OpenAPI, Management, and
  Flutter. Until a reviewed provider adapter is wired in, `supervised_live`
  emits a blocking finding and cannot advance past the guide.
- The historical `bootstrap.azure.admin-v1` pack did not permit creating or
  deleting the v2 custom role definition. This is resolved without mutating
  the old pack: active guided bootstrap now pins `bootstrap.azure.admin-v2`,
  which adds the exact role-definition write/delete boundary. Broad
  `Contributor` plus `User Access Administrator` fallback remains forbidden.
- The historical `bootstrap.aws.admin-v1` pack attempted to attach the
  `thesis-demo-v2` actions as an IAM-user inline policy. Even a compact action
  document exceeds AWS's 2,048-character aggregate user-inline-policy quota.
  This is resolved without rewriting v1: active guided bootstrap now pins
  `bootstrap.aws.admin-v2`, which creates one gate-owned customer-managed
  policy, attaches it only to the generated user, and includes the exact
  version/detach/delete cleanup boundary. Its rendered document must stay
  below the 6,144-character managed-policy limit.
- The frozen AWS `thesis-demo-v2` descriptor says "generated deployment role",
  while the implemented CloudConnection and Terraform provider boundary use a
  generated IAM-user access key. This is resolved without rewriting the frozen
  permission inventory: active guided setup additionally pins the versioned
  `aws.thesis-demo-v2.iam-user-v1` identity binding. The composite digest binds
  that IAM-user/access-key/customer-managed-policy assignment to the exact v2
  permission-pack digest and adds the IAM-user self-inspection actions used by
  the Deployer preflight. AssumeRole remains explicit future work rather than
  an unimplemented claim of the PoC.
- The existing guided session has no provider-identity deletion lifecycle.
  Deleting a local CloudConnection alone is not cleanup, so the disposable
  live runner needs its own provider cleanup ledger and operation.
- Immediate disposal of a submitted bootstrap credential is correct for a
  persistent production connection but conflicts with a disposable
  create/verify/delete test. The test runner therefore keeps bootstrap
  authority only in process memory until cleanup; it does not change the
  normal application disposal contract.
- GCP existing-project and organization/project-creation paths cannot share
  one initial result. Only the existing-project path is admitted first.
- The historical GCP v1/v2 packs remain evidence, but the active existing-
  project path now pins `bootstrap.gcp.admin-v3`. It retains the v2 inspection
  and role-reconciliation permissions and adds only
  `serviceusage.services.enable` plus `serviceusage.operations.get` for the
  fixed 19-service `gcp.phase8-api-baseline.v1`. The setup manifest digest
  binds both artifacts. Cleanup treats `deleted=true` as the correct immediate
  custom-role result and intentionally leaves the shared API baseline enabled.
- The Deployer credential checkers now select the exact synchronized
  `thesis-demo-v2` inputs whenever the CloudConnection carries that version;
  missing and historical versions retain the legacy matrices only for
  compatibility and fail the normalized version gate. AWS and Azure use
  separate versioned identity bindings for the metadata reads required by
  their implemented IAM-user and service-principal self-inspection paths.
  GCP tests the project-safe v2 permissions directly and checks every service
  in the frozen API baseline through Service Usage; any missing service is a
  blocking preflight result rather than a deferred Terraform mutation.
  This is offline implementation evidence, not live G4 provider evidence.
- The former GCP API-ownership inconsistency is resolved offline according to
  the approved
  [`GCP Phase 8 API Enablement Ownership`](2026-08-24_gcp_phase8_api_ownership.md)
  plan: bootstrap v3 owns the fixed existing-project superset, the generated
  v2 identity verifies it, and active v2 Terraform contains no API-enablement
  resources. G6/G7 remain blocked on supervised G2-G5 provider evidence, not
  on unresolved local ownership.

## 3. Gate Sequence

| Gate | Provider contact | Mutations | Cost-bearing workload resources | Required result |
|---|---|---|---|---|
| G0 Static/offline | None | None | None | Contract digests, permission inventories, redaction, schema, and cleanup logic pass |
| G1 Local full-stack smoke | None | Local ephemeral DB/containers only | None | UI -> Management -> deterministic adapter -> encrypted test CloudConnection passes |
| G2 Authority smoke | AWS/Azure/GCP | None | None | Submitted bootstrap credential resolves to the exact selected account, tenant/subscription, or project and satisfies the bootstrap authority pack |
| G3 Setup-only apply | One provider at a time | IAM/directory identity, policy/role, one generated credential; GCP also enables the pinned public-service baseline | None | A unique `twin2mc-e2e-*` deployment identity is created idempotently from the v2 pack and GCP API state matches the reviewed baseline |
| G4 Non-admin validation | One provider at a time | None | None | Generated credential authenticates, matches the selected scope, and passes normalized provider/deployer preflight |
| G5 Identity cleanup | One provider at a time | Delete only gate-owned key, binding/policy, role where owned, and identity | None | Provider lookup proves absence or the documented inactive/deleted terminal state; test CloudConnection and local secret material are removed |
| G6 Terraform plan-only | One provider at a time | Provider reads and local plan artifacts only | None | The bounded credential can produce the chosen Small single-cloud plan; no `apply` |
| G7 Paid deployment smoke | One provider at a time | Small single-cloud architecture | Yes | Explicitly approved deploy, health/evidence, destroy, and leak check |
| G8 Multi-cloud matrix | Two or three providers | Approved architecture resources | Yes | Only admitted after the corresponding providers pass G2-G7 separately |

G0 and G1 remain normal automatic gates. G2-G8 remain opt-in. G3 is the
earliest gate allowed to mutate a provider.

The isolated G1 command is:

```bash
./thesis.sh test setup-smoke
```

It starts one short-lived Management API with an ephemeral SQLite database,
forces `deterministic_fake`, mounts no cloud-credential overlay, drives the
shared Flutter bootstrap UI through the real API client, covers all three
provider client paths, and scans API logs and persistence for the submitted
secret sentinel before removing the container. Credential/auth rate limiting
is disabled only inside this isolated functional smoke so repeated flow cases
remain deterministic; the normal runtime and dedicated backend tests retain
rate-limit coverage.

## 4. Provider Identity-Only Scope

### AWS

Allowed:

- `sts:GetCallerIdentity` and exact account comparison;
- create/reconcile one prefixed IAM deployment user;
- create and attach only the frozen `thesis-demo-v2` customer-managed policy;
- create exactly one test access key;
- authenticate the generated key and run read-only preflight;
- detach and delete the exact access key, gate-owned managed policy versions,
  managed policy, and test user.

Forbidden in this gate: Organizations, Identity Center activation, IoT,
Lambda, Step Functions, DynamoDB, S3, Kinesis, SNS, SQS, TwinMaker, Grafana,
ECR, CodeBuild, or any workload resource.

### Azure

Allowed:

- resolve the exact tenant and subscription from the bootstrap principal;
- create/reconcile one prefixed Entra application and service principal;
- create one short-lived test client secret;
- create/reuse the reviewed v2 custom role definition and assign it only at the
  planned subscription/test scope;
- include only the three `azure.thesis-demo-v2.service-principal-v1`
  self-inspection reads needed to resolve the subscription, list its locations,
  and read the assigned role definition;
- authenticate the generated service principal and run read-only preflight;
- remove the exact assignment, owned role definition, service principal,
  application, and test secret.

Subscription `Owner` alone is not sufficient evidence for Entra application
creation. The gate validates directory and ARM authority separately. No
resource group or managed service is created.

### GCP

The first gate covers the **existing billing-enabled project** path only. The
organization/project-creation path is a later independent gate because it has
different organization, folder, and billing authority.

Allowed:

- resolve and compare the exact project;
- create/reconcile one prefixed service account;
- verify the three bootstrap-prerequisite APIs and idempotently enable the
  exact 19-service Phase 8 baseline through Service Usage;
- create/reuse the reviewed v2 project custom role and binding;
- create exactly one user-managed test key when organization policy permits;
- authenticate the generated service account and run read-only preflight;
- remove the key, binding, owned custom role, and service account.

The gate must not enable anything outside the pinned baseline and must not
weaken an organization policy that forbids user-managed keys. A missing
bootstrap-prerequisite API or key-policy block is a truthful gate result, not
permission to change the project or policy. GCP role cleanup succeeds when the
binding is absent and the exact owned role reports `deleted=true`; its run ID
is not reused during the seven-day recovery window. Public-service enablement
creates no Twin workload and is retained because disabling shared project APIs
during identity cleanup would be destructive.

## 5. Required Test Cases

Every provider must pass the following cases before G6:

1. Correct bootstrap authority resolves to the expected provider scope.
2. Wrong account, tenant/subscription, or project fails before mutation.
3. Incomplete bootstrap authority returns a typed, redacted permission finding.
4. First execution creates exactly one uniquely named deployment identity and
   one generated credential.
5. Repeating the same idempotency key does not create another identity or key.
6. A conflicting request cannot reuse the same session or generated identity.
7. The generated credential authenticates as the new non-admin identity, not
   as the bootstrap principal.
8. The generated credential carries `thesis-demo-v2`; AWS/Azure self-inspection
   and GCP project-testable permissions pass the version-aware normalized
   permission/preflight contract, with every deferred provider-operation check
   retained as a warning.
9. Bootstrap secret sentinels are absent from database rows, API responses,
   application logs, Flutter state, exports, and captured evidence.
10. A forced failure after each provider mutation can be reconciled or cleaned
    without deleting pre-existing identities.
11. Cleanup deletes only resources bearing the gate run ID and recorded
    provider identifiers.
12. Provider lookup after cleanup returns not found or the provider's explicit
    inactive/deleted terminal state (GCP custom role: `deleted=true`); local
    test CloudConnection and temporary secret files are absent.

## 6. Credential And Evidence Rules

- Bootstrap credentials are supplied only at the supervised request boundary.
- Credentials and generated secrets are never command-line arguments, test
  parameters, pytest node IDs, screenshots, or CI secrets for the default
  workflow.
- The runner uses an in-memory value or a mode-`0600` temporary file and
  removes it in `finally`/trap cleanup.
- Shell tracing is forbidden. Provider exception bodies are mapped to typed
  safe findings before persistence or output.
- Evidence records provider, target scope, permission-pack ID/digest, run ID,
  state transitions, safe provider object IDs, timestamps, and pass/fail only.
- Existing user-owned bootstrap credentials are never revoked automatically.
  A dedicated disposable credential may be revoked only when its exact owner
  and key/secret ID are proven.
- A test identity is never promoted silently into a reusable deployment
  connection. Promotion requires an explicit supervised decision; otherwise
  cleanup is mandatory.

## 7. Cleanup Transaction

The live runner owns a durable local cleanup ledger containing only safe
identifiers:

```text
run_id, provider, target_scope,
generated_identity_id, generated_credential_id,
policy_or_role_id, binding_or_assignment_id,
cloud_connection_id, current_cleanup_step
```

Cleanup runs on success, failure, interruption, and the next invocation when a
stale ledger exists. Deletion order is provider-specific and idempotent. The
runner refuses cleanup when an object lacks the exact gate prefix/run ID or
does not match the ledger. A cleanup failure blocks every later live gate and
produces a manual provider-console checklist with safe identifiers only.

The bootstrap credential must remain request-memory-only for the duration of
an ephemeral create/verify/delete test. The normal application flow may release
it immediately after a successful persistent CloudConnection is created; that
persistent identity is then lifecycle-managed separately and is not the first
disposable G3 test identity.

## 8. Implementation Slices

### Slice A — Gate Contract And Offline Harness

Implemented and credential-free as of 2026-08-24.

- Add an explicit live-gate manifest with provider, expected scope,
  permission-pack digests, unique run ID, `plan_only`/`setup_only` mode, and
  mandatory cleanup policy.
- Add offline schema, redaction, prefix-ownership, stale-ledger, partial-failure,
  and command-guard tests.
- Make the runner refuse execution unless one provider and one mode are
  explicit; never add it to default CI.
- Materialize the frozen provider-neutral deployment inputs into deterministic
  provider-native AWS policy, Azure custom-role, and GCP custom-role request
  documents. Verify exact action preservation, provider scope, AWS policy
  size, mandatory conditions, ownership naming, and absence of secret fields
  without contacting a provider.

### Slice B — Reviewed Live Provider Adapters

Partially implemented, not enabled. The synchronized `supervised_live` mode
and its fail-closed UI/Management boundary are implemented. An SDK-independent
adapter orchestrator now derives an ownership-bounded run ID, dispatches one
provider at a time, admits only a validated `thesis-demo-v2` CloudConnection,
and requires a typed secret-free rollback receipt. It compensates a generated
credential that fails this boundary before returning it. Provider-native
policy materialization is now one shared, provider-SDK-free Management module
backed only by synchronized generated contracts; the repository CLI reuses
that module. Version-aware Deployer
permission selection are implemented offline. The Azure materializer now
combines the immutable workload inventory with the separately pinned
`azure.thesis-demo-v2.service-principal-v1` self-inspection reads. Provider
implementations and live G2-G5 evidence remain pending. GCP API
ownership is resolved offline; G6/G7 wait for that live setup evidence.

The concrete SDK drivers, generated-credential provider validation, and the
compensating cleanup handoff for a later local persistence failure are still
pending. Until all three exist, the runtime factory intentionally selects the
unconfigured adapter and the guide stays blocking.

- Keep the resolved AWS IAM-user binding, AWS/Azure v2 bootstrap boundaries,
  and separate exact GCP v3 plus API-baseline digests pinned before provider
  code is enabled.
- [x] Add a synchronized `supervised_live` mode while retaining production
  default `disabled` and test default `deterministic_fake`; keep it blocked
  until the reviewed provider adapters below replace the fail-closed boundary.
- Implement AWS, Azure, and GCP adapters against the pinned authority and
  deployment-pack digests.
- [x] Add the shared SDK-independent adapter transaction, exact target/result
  validation, and secret-free provider rollback receipt; keep concrete SDK
  drivers and Management persistence compensation pending.
- [x] Make the provider-native documents importable by Management from the
  synchronized generated contracts; the CLI and future adapters share this
  implementation and must not maintain a second hand-written policy inventory.
- Keep provider calls in Management; Flutter remains a typed client only.
- Validate the generated credential before persisting its encrypted
  CloudConnection.
- Do not call workload-service APIs from the adapter.

### Slice C — Setup-Only Live Runner And Cleanup

- Drive guide -> session -> execute -> CloudConnection -> preflight through the
  real Management API.
- Capture the provider mutation ledger outside normal API/log output.
- Provide provider-specific cleanup and post-cleanup absence checks.
- Add a `--plan-only` dry run and a separate unmistakable live confirmation;
  neither may accept secrets on the command line.

### Slice D — Supervised Provider Execution

- Run G2-G5 for one provider at a time.
- Review findings and update only the affected permission pack/adapter.
- Repeat from a clean provider state until the setup-only gate is zero-finding.
- Run G6 only after G5 cleanup has been proven.

### Slice E — Paid Small Single-Cloud Admission

- Select one provider/profile/scenario explicitly.
- Record expected resources, maximum duration, cleanup command, and budget
  before `apply`.
- Deploy, capture thesis evidence, destroy, and verify absence before moving to
  another provider or multi-cloud pair.

## 9. Acceptance Criteria

- [ ] Default tests and CI remain credential-free and cannot select a live adapter.
- [ ] AWS, Azure, and GCP setup-only gates are independently selectable.
- [ ] A live gate cannot create workload resources and cannot mutate any GCP
  service outside the fixed API-baseline allowlist.
- [ ] Generated identities use the exact frozen `thesis-demo-v2` pack digest.
- [ ] Admin/bootstrap secrets never persist or appear in evidence.
- [ ] Generated non-admin credentials authenticate and pass normalized preflight.
- [ ] Idempotency and every tested partial-failure boundary avoid duplicate keys/identities.
- [ ] Cleanup proves provider and local absence or the provider's documented
  inactive/deleted terminal state after every disposable run.
- [ ] GCP existing-project is the only admitted live path; organization/project
  creation fails closed and is reported as future work.
- [ ] No Terraform apply or paid architecture resource occurs before explicit G7 admission.

## 10. Commands That Remain Forbidden By Default

The following are never automatic and are not part of a normal pull-request
gate:

- provider-authenticated G2-G6 commands;
- any bootstrap `--apply` invocation;
- Terraform `apply` or `destroy`;
- `pytest -m live` or existing Deployer E2E runners;
- organization, billing, directory, or Identity Center mutations;
- any command that reads or prints credential values for inspection.
