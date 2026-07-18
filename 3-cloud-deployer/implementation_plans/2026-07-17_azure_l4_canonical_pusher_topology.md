---
title: "Implementation Plan: Canonical Azure L4 Pusher Topology"
description: "Hardens the five-layer baseline to one executable and fail-closed Azure Digital Twins update path."
tags: [implementation-plan, deployer, azure, digital-twins, security, reliability]
lastUpdated: "2026-07-17"
version: "1.1"
---

# Implementation Plan: Canonical Azure L4 Pusher Topology

**Date:** 2026-07-17  
**Scope:** `3-cloud-deployer`, canonical developer documentation  
**Base branch:** `master`  
**Implementation branch:** `codex/pricing-tier-finalization`  
**GitHub issue:** [#117 Canonicalize the Azure Digital Twins update path](https://github.com/TVJunkie724/master-thesis/issues/117)  
**Plan status:** Reviewed and implementation-ready  
**Implementation status:** Implemented, reviewed, and verification-approved

---

## 1. Decision

The hardened `five-layer-baseline@1` has exactly one executable path for
updating Azure Digital Twins:

```text
L2 Persister (AWS, Azure, or GCP)
  -> authenticated HTTPS request
  -> Azure L0 ADT Pusher
  -> Azure SDK with managed identity
  -> Azure Digital Twins
```

The historical `adt-updater` Event Grid function is not part of the deployed
topology. It is removed from active source, the function registry, packaging,
naming, tests, Terraform commentary, and canonical documentation.

Whenever `layer_4_provider` is `azure`, the ADT update is a required outcome of
the current synchronous baseline. A missing ADT Pusher endpoint, missing token,
or failed ADT request must therefore fail the Persister invocation after the
idempotent storage write. The platform must not report a successful update
while silently leaving operational storage and the digital twin out of sync.

This slice does not introduce a queue, event broker, replay store, dead-letter
queue, or a new Eventing Layer. Those capabilities belong to the separately
planned architecture profile in Phase 8. Until then, visible failure plus the
existing sender retry boundary is the bounded baseline behavior.

---

## 2. Current Evidence

The repository currently contains two conflicting architecture descriptions:

1. Terraform deploys an Azure Digital Twins instance and an Azure L0 Function
   App, but no dedicated L4 Function App and no ADT Event Grid subscription.
2. The function registry, package tests, naming helpers, and historical source
   still describe and package an `adt-updater` Event Grid function.
3. Terraform already configures every L2 Persister to call the ADT Pusher when
   L4 is Azure:
   - Azure L2 through `azure_compute.tf`;
   - AWS L2 through `aws_compute.tf`;
   - GCP L2 through `gcp_compute.tf`.
4. The registry gives `adt-pusher` no activation boundary. As a result, any
   deployment involving Azure can package the Pusher even when L4 is not Azure.
5. All three Persisters currently swallow ADT delivery failures. Storage may
   succeed while ADT remains stale without an error reaching the caller.
6. The ADT Pusher compares its shared token directly, logs the complete request
   payload, and returns raw exception messages.

These are active runtime and contract defects, not documentation-only debt.

---

## 3. Target Contracts

### 3.1 Topology Contract

```text
providers.layer_4_provider != "azure"
  -> ADT Pusher is absent from provider packages
  -> Persister does not attempt an ADT update

providers.layer_4_provider == "azure"
  -> Azure L0 package contains exactly one ADT Pusher implementation
  -> active L2 Persister receives HTTPS endpoint and token
  -> Persister performs storage write and required ADT push
  -> ADT Pusher authenticates the request
  -> ADT Pusher updates ADT with managed identity
```

The Pusher activation is expressed as generic registry metadata:

```text
target_provider_key = "layer_4_provider"
target provider      = "azure"
```

L0 functions must have exactly one activation mode:

- a cross-cloud `boundary`; or
- an explicit `target_provider_key`.

There is no implicit "always package for this provider" fallback.

### 3.2 Delivery Contract

The baseline ordering remains:

```text
persist idempotent storage item
  -> update ADT
  -> invoke optional event checking
  -> acknowledge success
```

Storage item IDs are deterministic (`device_id` plus canonical timestamp) and
the provider writes are idempotent:

- AWS DynamoDB: `put_item` to the same primary key;
- Azure Cosmos DB: `upsert_item`;
- GCP Firestore: `set` on the same document ID.

If the ADT update fails after storage succeeds, the Persister fails. An upstream
retry repeats an idempotent storage write before retrying ADT. This does not
provide durable replay or exactly-once delivery; the limitation must remain
explicit until Phase 8.

### 3.3 Error Contract

| Boundary | Required behavior |
| --- | --- |
| L4 is not Azure | ADT configuration is not required and no push occurs. |
| L4 is Azure, URL or token missing | Raise a deterministic configuration error before success is returned. |
| ADT Pusher returns 4xx/5xx or network retry is exhausted | Raise a stable ADT delivery error; do not swallow it. |
| Invalid request JSON | Return HTTP 400 with a generic stable error body. |
| Missing device ID or telemetry | Return HTTP 400 without echoing payload content. |
| Missing Pusher runtime configuration | Return HTTP 500/503 with a generic stable error body. |
| Invalid token | Return HTTP 401 using constant-time comparison. |
| Azure SDK validation failure | Return HTTP 400 without returning raw provider text. |
| Unexpected Azure SDK/runtime failure | Return HTTP 500 without returning raw exception text. |

Runtime logs may include provider, function, status class, and exception type.
They must not include inter-cloud tokens, complete telemetry payloads, provider
response bodies, or raw exception strings that can contain secrets.

### 3.4 Authentication Contract

The existing `X-Inter-Cloud-Token` mechanism remains the baseline authentication
method for this slice. The Pusher must use the shared Azure token validator, and
that validator must use `hmac.compare_digest`.

Azure Digital Twins access remains managed-identity based through
`DefaultAzureCredential`. No static Azure credential may be added to the
Function App.

Replacing the shared token with a stronger workload identity contract is tracked
separately and is not hidden inside this topology cleanup.

---

## 4. Scope

### In Scope

- Remove the dead Azure `adt-updater` runtime source and every active reference.
- Remove the dead Azure L4 bundler API.
- Remove unused Azure function naming helpers whose names are owned by the
  function registry.
- Introduce explicit target-layer activation metadata for non-boundary L0
  functions.
- Bind `adt-pusher` inclusion exclusively to Azure as the selected L4 provider.
- Make Azure L4 configuration and delivery mandatory in AWS, Azure, and GCP
  Persisters.
- Harden ADT Pusher authentication, logging, request validation, and errors.
- Align Terraform comments and source-contract tests with the executable path.
- Add exact same-cloud and cross-cloud package matrix tests.
- Update canonical developer/runtime documentation and roadmap status.

### Out of Scope

- Event Hub, Event Grid, Service Bus, Pub/Sub, EventBridge, queues, replay, or
  dead-letter handling.
- A new Eventing and Messaging Layer.
- Live Azure deployments or tests that create cloud resources.
- A general dynamic architecture engine.
- Provider service-tier propagation from Optimizer to Terraform; that is the
  next pre-Phase-8 blocker in issue #118.
- New Flutter behavior.
- A new credential mechanism.

---

## 5. Implementation Slices

### Slice 1: Registry Activation and Dead Artifact Removal

**Files:**

- `src/function_registry.py`
- `src/providers/azure/azure_functions/adt-updater/`
- `src/providers/azure/azure_bundler.py`
- `src/providers/azure/layers/function_bundler.py`
- `src/providers/azure/naming.py`
- related registry, package-builder, bundler, and ZIP tests

**Changes:**

1. Add optional `target_provider_key` metadata to `FunctionDefinition`.
2. Validate that every L0 definition has exactly one of `boundary` or
   `target_provider_key`.
3. Configure `adt-pusher` with
   `target_provider_key="layer_4_provider"`.
4. Make `get_l0_for_config` include target-activated functions only when the
   configured target provider equals the package target.
5. Replace set-based result deduplication with order-preserving deduplication so
   registry order and deterministic package output remain stable.
6. Remove `adt-updater` from the L4 registry and delete its source directory.
7. Remove `bundle_l4_functions` and its compatibility re-export.
8. Remove stale Azure L4 function and Event Grid naming helpers. The registry
   remains the single source of truth for static function names.

**Required tests:**

- all-Azure includes `adt-pusher` exactly once;
- AWS L2 to Azure L4 includes `adt-pusher` exactly once;
- GCP L2 to Azure L4 includes `adt-pusher` exactly once;
- Azure L1 with non-Azure L4 excludes `adt-pusher`;
- non-Azure packages exclude both `adt-pusher` and `adt-updater`;
- no selected configuration returns `adt-updater`;
- aggregate L0 ZIP contains the Pusher implementation when required;
- no generated individual or aggregate package contains `adt-updater`.

### Slice 2: Required Provider-Neutral ADT Delivery

**Files:**

- AWS Persister
- Azure Persister
- GCP Persister
- focused provider contract tests

**Changes:**

1. Determine the requirement from
   `DIGITAL_TWIN_INFO.config_providers.layer_4_provider`.
2. If L4 is not Azure, skip ADT delivery even if stale environment variables
   are present.
3. If L4 is Azure, require a non-empty HTTPS Pusher URL and token.
4. Build the same Pusher payload for all three providers.
5. Propagate exhausted delivery failure through a stable error type.
6. Remove all "ADT is secondary" and "non-fatal" behavior.
7. Preserve deterministic storage IDs and current event-checking order.
8. Do not expose raw transport or provider errors in HTTP response bodies.

**Required tests per provider:**

- non-Azure L4 skips Pusher;
- Azure L4 with missing provider mapping fails;
- Azure L4 with missing URL fails;
- Azure L4 with missing token fails;
- Azure L4 sends the normalized payload;
- delivery failure propagates;
- successful delivery still permits the event-checking path;
- a retry repeats the same deterministic storage key.

Tests may use import helpers and mocked provider clients, but must execute the
real Persister decision and payload-building code. Source-text assertions are
not sufficient for runtime behavior.

### Slice 3: ADT Pusher Security and Error Boundary

**Files:**

- `src/providers/azure/azure_functions/adt-pusher/function_app.py`
- `src/providers/azure/azure_functions/_shared/inter_cloud.py`
- `src/providers/azure/azure_functions/_shared/adt_helper.py`
- focused ADT Pusher and shared-helper tests

**Changes:**

1. Reuse `validate_token` from the shared Azure module.
2. Implement token comparison with `hmac.compare_digest`.
3. Remove full request-body logging.
4. Validate that parsed JSON and an unwrapped envelope payload are objects.
5. Require `telemetry` to be a non-empty object; scalar and list payloads are
   rejected instead of being passed to the patch builder.
6. Return stable error codes and generic messages.
7. Log only safe diagnostic metadata.
8. Update helper documentation to name only the canonical Pusher caller.

**Required tests:**

- valid, invalid, missing, and unconfigured tokens;
- constant-time validator behavior through the public helper;
- invalid JSON;
- non-object request and envelope payload;
- missing device ID;
- empty telemetry;
- successful mapped twin update;
- validation error redaction;
- unexpected SDK error redaction;
- no response or captured log contains injected secret/error text.

### Slice 4: Terraform and Documentation Contract

**Files:**

- `src/terraform/azure_twins.tf`
- `src/terraform/azure_glue.tf`
- `src/terraform/azure_compute.tf`
- `src/terraform/aws_compute.tf`
- `src/terraform/gcp_compute.tf`
- Terraform source-contract tests
- `docs-site/docs/components/deployer.md`
- `docs-site/docs/architecture/end-to-end-flows.md`
- `docs-site/docs/architecture/refactoring-roadmap.md`
- historical ADT implementation plan supersession note

**Changes:**

1. Describe the one canonical Persister-to-Pusher-to-ADT path.
2. Remove the commented ADT Event Grid topic from active Terraform source.
3. State that Pusher activation follows Azure L4, not "multi-cloud" generally.
4. Add a compact function-and-edge inventory to canonical developer docs.
5. Mark the historical Event Grid plan as superseded, while preserving it as
   historical evidence.
6. Mark issue #117 done only after all verification gates pass.

**Required source-contract assertions:**

- Azure L2 receives Pusher endpoint/token iff L4 is Azure;
- AWS L2 receives them iff L2 is AWS and L4 is Azure;
- GCP L2 receives them iff L2 is Google and L4 is Azure;
- Pusher has the ADT endpoint and managed identity;
- active Terraform has no `adt-updater` or ADT Event Grid subscription.

---

## 6. Verification Gates

### Focused Tests

```bash
docker --context orbstack compose exec -T 3cloud-deployer \
  python -m pytest -q \
  tests/unit/test_function_registry.py \
  tests/unit/terraform/test_package_builder_registry.py \
  tests/unit/terraform/test_function_bundler.py \
  tests/integration/test_azure_zip_validation.py \
  tests/unit/lambda_functions/test_persister.py \
  tests/unit/azure_functions/test_azure_inter_cloud.py \
  tests/unit/azure/test_adt_helper.py
```

New provider/Pusher contract tests must be included in this gate.

### Full Safe Deployer Suite

```bash
docker --context orbstack compose exec -T 3cloud-deployer \
  python -m pytest tests --ignore=tests/e2e -q
```

### Static and Security Gates

```bash
docker --context orbstack compose exec -T 3cloud-deployer \
  ruff check src tests --exclude tests/e2e
docker --context orbstack compose exec -T 3cloud-deployer bandit -r src -q
docker --context orbstack compose exec -T 3cloud-deployer python -m compileall -q src
docker --context orbstack compose exec -T 3cloud-deployer python -m pip check
```

### Terraform Gates

```bash
terraform fmt -check -recursive 3-cloud-deployer/src/terraform
terraform -chdir=<credential-free-temporary-module> init -backend=false
terraform -chdir=<credential-free-temporary-module> validate
```

Provider plugins may be reused from the local cache. No plan or apply may use
real credentials or contact cloud resource APIs.

### Documentation and Compose Gates

```bash
docker --context orbstack compose --profile docs run --rm docs mkdocs build --strict
docker --context orbstack compose config --quiet
```

### Static Absence Gate

The active runtime source must not contain any stale implementation reference.
Negative test assertions and explicitly superseded historical documents may
still name the removed artifact:

```bash
rg -n "adt-updater|bundle_l4_functions|adt_event_grid_subscription" \
  3-cloud-deployer/src
```

---

## 7. Review Checklist

### Architecture

- One executable Azure L4 update path exists.
- Registry metadata, package contents, Terraform, and docs agree.
- Same-cloud and cross-cloud are explicit test cases.
- No Phase 8 resource or abstraction is introduced.

### Reliability

- Required ADT delivery cannot be silently skipped or swallowed.
- Retried writes retain deterministic storage IDs.
- Baseline retry limitations are documented honestly.

### Security

- Token comparison is constant-time.
- Managed identity remains the ADT credential.
- Payloads, tokens, and raw provider errors are absent from logs/responses.
- HTTPS remains mandatory at the sender boundary.

### Maintainability

- Function names have one source of truth.
- L0 activation metadata is generic and validated.
- Dead compatibility APIs and naming helpers are removed.
- Tests execute behavior rather than only inspect source.

### Thesis Readiness

- The implementation preserves a reproducible five-layer baseline.
- Current limitations are stated without presenting Phase 8 as implemented.
- Historical plans are preserved but clearly marked as superseded.
- Canonical docs explain the running system, not research conclusions.

---

## 8. Structured Commits

1. `docs(deployer): plan canonical Azure L4 path`
2. `refactor(deployer): remove dead Azure ADT updater path`
3. `fix(deployer): enforce required Azure L4 delivery`
4. `docs(deployer): document canonical Azure L4 topology`

Every commit references issue #117. The issue closes only after the full safe
suite, static/security gates, Terraform validation, and strict documentation
build are green.

---

## 9. Definition of Done

- [x] `adt-updater` is absent from active source, packages, and canonical docs.
- [x] `adt-pusher` is included iff Azure is the configured L4 provider.
- [x] AWS, Azure, and GCP Persisters require successful ADT delivery for Azure L4.
- [x] Missing configuration and delivery failures fail visibly and safely.
- [x] Pusher authentication and error handling meet the security contract.
- [x] Same-cloud and both cross-cloud Azure L4 paths have behavioral coverage.
- [x] Terraform and package contracts agree with runtime behavior.
- [x] Full safe Deployer suite and all static/security gates pass.
- [x] Terraform validates without cloud credentials.
- [x] Strict MkDocs and Compose validation pass.
- [x] Canonical docs and roadmap are current.
- [x] Issue #117 contains verification evidence and is closed.

### Final Verification Evidence

- Deployer safe suite: `1517 passed, 1 skipped`
- Focused topology/package/runtime matrix: `198 passed, 1 skipped`
- Persister/Pusher runtime contract: `97 passed`
- Ruff on production and safe tests: passed
- Bandit on production source: passed
- Python compile and dependency checks: passed
- Terraform format and credential-free validation: passed
- Strict MkDocs build and Compose validation: passed
- Live cloud E2E: intentionally not executed
