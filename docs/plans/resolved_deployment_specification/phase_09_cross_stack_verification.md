# Phase 9: Cross-Stack Drift Gate

**Issue:** [#128](https://github.com/TVJunkie724/master-thesis/issues/128)
**Status:** Implemented and locally verified; focused branch CI pending
**Blocked by:** #61, #120, #127, #129, #130, #131, #132, #133, #134, #135, #136, #137

This is Resolved Deployment Specification subphase 9 and the final hardening
gate for that mini-roadmap. It is not repository architecture Phase 8.

## 0. Git And Delivery

- **Branch:** `codex/pricing-tier-finalization`
- **Base branch:** `master`
- **Commit prefix:** `[AI-0717-rds9]`
- **Cloud mutation:** forbidden
- **Live provider credentials:** forbidden
- **Primary command:** `./thesis.sh test deployment-contract`

The implementation is complete only after the command succeeds from the
repository root and the same focused drift gate runs in CI. Native
Windows/Linux/macOS release evidence remains owned by the existing
`flutter-platforms.yml` matrix because one host cannot build every native
desktop target.

## 1. Target And Boundary

Prove that every deployment-enforceable value selected by the cost model
retains the same identity and value through all executable boundaries:

```text
fixed workload + immutable pricing catalogs
  -> Optimizer formula and deployment selections
  -> ResolvedDeploymentSpecification v1 + digest
  -> Management validation, persistence, and selected run
  -> DeploymentManifest v2 in the operation package
  -> Deployer manifest validation and preflight
  -> allowlisted typed tfvars
  -> Terraform variable validation and resource binding
```

The gate verifies the existing closed-world five-layer baseline. It does not
introduce architecture profiles, Eventing, a dynamic layer engine, cloud API
calls, `terraform apply`, simulator E2E, or final post-refactoring E2E.

## 2. Verification SSOT

Add
`contracts/resolved-deployment-specification/v1/verification-matrix.json`.
It is synchronized byte-for-byte with the existing contract copies in
Optimizer, Management API, and Deployer by
`scripts/sync_resolved_deployment_contract.py`.

The matrix contains only verification inputs and hard expected outcomes:

- representative provider paths;
- Azure IoT Hub workload, SKU, and capacity cases;
- exact standard and transition runtime profiles;
- exact cool/archive storage classes and schedules;
- storage-transition ownership rules;
- expected Terraform target/value pairs.

It contains no credentials, endpoints, timestamps, mutable catalog responses,
or provider payloads. Runtime code does not read this file. It is a
test/evidence SSOT, while `deployment-dimensions.json` remains the production
deployment registry.

Independent tests may construct specifications from the production registry,
but expected values must come from the verification matrix. No test may derive
both actual and expected values through the same production function.

## 3. Scenario Matrix

### Representative Complete Paths

| ID | Required path evidence |
| --- | --- |
| `all-aws` | all seven slots; DynamoDB PAY_PER_REQUEST; S3 STANDARD_IA and DEEP_ARCHIVE; AWS standard/mover runtime values |
| `all-azure` | all seven slots; IoT Hub SKU/capacity; Cosmos serverless; Blob Cool/Archive; Azure plan and timer values |
| `mixed` | canonical AWS/Azure/GCP fixture; all required receiver glue; source-owned transition runtimes |
| `gcp-storage` | supported AWS/Azure L4/L5 with GCP hot/cool/archive; Firestore, Nearline, Archive, and GCP mover values |

### Azure IoT Hub Formula-To-Terraform Cases

| Workload messages | Expected SKU | Expected capacity |
| ---: | --- | ---: |
| 200,000 | F1 | 1 |
| 12,000,001 | S1 | 2 |
| 180,000,000 | S2 | 1 |
| 45,000,000,000 | S3 | 5 |

For every case, the Optimizer formula result, L1 deployment selection,
specification dimensions, translated tfvars, Terraform variable validation,
and resource binding must agree.

### Storage Transition Matrix

Generate all 27 `(hot, cool, archive)` provider triples from
`aws`, `azure`, and `gcp`, while keeping the remaining slots on a supported
path. For each triple assert:

1. hot-to-cool runtime provider equals the hot/source provider;
2. cool-to-archive runtime provider equals the cool/source provider;
3. runtime component IDs, memory, scale values, and schedules equal the
   verification matrix;
4. destination storage classes equal the selected cool/archive provider;
5. each cross-provider boundary has exactly the receiver-provider glue
   component required by the registry;
6. same-provider boundaries do not create unnecessary glue;
7. translated tfvars contain exactly the selected allowlisted targets and no
   evidence-only dimensions.

This covers all nine source/destination pairs at both storage boundaries.

### Negative Matrix

Every canonical invalid fixture must fail in Optimizer/contract validation,
Management validation or selection, and Deployer preflight as applicable.
Explicit named assertions cover:

- legacy or missing specification;
- unsupported schema version;
- missing/duplicate/unknown component or dimension;
- provider/slot/path mismatch;
- altered value and unsupported SKU/capacity combination;
- missing, wrong-provider, or reordered transition runtime;
- missing or unnecessary cross-cloud glue;
- unbound formula/evidence reference;
- digest/run identity mismatch;
- secret-like and unknown fields.

Errors must be bounded, machine-identifiable, and must not echo the rejected
value, credential-shaped data, local path, or provider payload.

## 4. Project Assertions

### Optimizer

Add focused tests that use real formula/layer calculation code and assert:

- Azure workload tiers produce the four exact SKU/capacity pairs;
- standard and mover deployment selections use the exact matrix values;
- AWS Deep Archive and GCP Archive are emitted as deployment selections;
- the selected path produces a schema-valid, digest-valid specification;
- all storage triples build the required source runtimes and receiver glue;
- unknown values fail before a result is publishable.

### Management API

Add focused tests that assert:

- canonical and generated matrix specifications validate without rewriting;
- JSON persistence round-trips the exact specification and digest;
- selecting a run preserves run/specification identity;
- package creation embeds that exact selected specification in Manifest v2;
- provider projection drift, legacy state, tampering, and ambiguous selection
  fail before credential resolution or package staging.

Tests use isolated SQLite transactions and fake Optimizer/Deployer clients.
They do not start deployment streams or contact another service.

### Deployer

Add focused tests that assert:

- every matrix specification passes strict Manifest v2 validation;
- all 27 storage triples translate to the exact target/value map;
- Azure F1/S1/S2/S3 values translate without coercion;
- non-deployable evidence never becomes a tfvar;
- manifest/preflight negatives fail before package building, Terraform init,
  or credential checks;
- every registry Terraform target has exactly one declared variable,
  fail-closed validation, and explicit resource/local binding;
- source-owned transition and receiver-owned glue resources match the matrix.

Terraform verification has three credential-free levels:

1. `terraform fmt -check` and `terraform validate` on the canonical source;
2. source-binding tests that map every allowlisted target to a variable and
   resource/local consumer;
3. representative `terraform test` plan runs with native mock providers when
   the current Terraform configuration can evaluate without cloud/runtime
   artifacts.

If a representative mock plan cannot evaluate because a required package file
is intentionally produced only by preflight, the test must create that
ephemeral artifact through the real package builder. It may not skip the plan,
use live credentials, or weaken resource expressions.

### Flutter

The phase reuses Phase 8 behavior and runs its full gates. No new UI is added.
The selected specification must remain read-only, digest-bound, and
fail-closed on unsupported versions or stale responses.

## 5. Repository Command

Add `scripts/verify_resolved_deployment_drift.py` and wire it to:

```bash
./thesis.sh test deployment-contract
```

The script:

1. refuses credential overlays and `RUN_E2E_TESTS=1`;
2. validates Compose and synchronized contract copies;
3. runs focused cross-stack tests first for fast, field-specific feedback;
4. runs complete safe Optimizer, Management, Deployer, Flutter, docs, and
   static/security gates;
5. runs Terraform formatting, validation, source bindings, and mock plans;
6. prints stable stage names, elapsed time, and the failing command;
7. exits non-zero on the first failed stage;
8. never writes credentials, tfstate, plans, or tfvars into tracked paths.

Temporary workspaces use the operating-system temp directory and are removed
on success and failure. The script accepts `--focused` only for CI/developer
diagnosis; the documented no-argument command remains the complete gate.

## 6. Required Quality Gates

### Focused Cross-Stack Gate

- verification-matrix schema and synchronized-copy tests;
- Optimizer formula/specification matrix tests;
- Management persistence/selection/manifest matrix tests;
- Deployer validation/tfvars/source/mock-plan matrix tests;
- root script unit tests, command discovery, and safety refusal tests.

### Full Safe Gate

- Optimizer: full pytest, Ruff, Bandit, compileall;
- Management API: full non-E2E pytest, Ruff, Bandit, compileall, migrations;
- Deployer: full non-E2E pytest, Ruff, Bandit, compileall;
- Terraform: fmt, validate, target coverage, representative mock plans;
- Flutter: formatter, analyzer, architecture gate, full tests, Web release,
  and host desktop build;
- CI: existing native macOS/Windows/Linux release matrix;
- docs: strict MkDocs;
- repository: Compose config, `git diff --check`, secret-like-field scan, and
  stale hardcoded-value scan.

No gate may make a provider SDK request. E2E directories and `live` markers
remain excluded even when credentials exist on the host.

## 7. Documentation And Evidence

Update:

- this mini-roadmap and refactoring roadmap;
- canonical architecture and state/data-flow documentation;
- Optimizer result/extension contract;
- Management persistence and selection contract;
- Deployer manifest, preflight, tfvars, and provider matrices;
- testing guide and `thesis.sh` handbook;
- Flutter deployment-review guide only where gate behavior affects users;
- a thesis-method evidence document explaining why functional
  completeness and cost-to-deployment reproducibility are validity gates.

Developer documentation describes the implemented system. Thesis evaluation,
research questions, and architectural interpretation remain in thesis evidence
documents, not the operational user guide.

## 8. Review Procedure

Review pass 1 checks:

- scenario and target coverage;
- cross-project identity/digest continuity;
- source ownership and receiver glue;
- negative behavior and redaction;
- command safety and deterministic cleanup.

Review pass 2 starts from the Definition of Done and independently checks:

- no project-specific test builder can silently disagree with the shared
  verification matrix;
- no supported target is unbound or multiply bound;
- no platform gate is claimed without local or CI evidence;
- documentation matches executable commands and present behavior.

All findings are fixed and both passes rerun before commit.

### Completed Review Evidence

Review pass 1 found and fixed:

- nullable Terraform validation that could evaluate invalid null comparisons;
- an unconditional Azure 3D-scene output reference;
- missing explicit `terraform validate` evidence;
- local cache/credential exposure in the Deployer image context;
- a dynamically interpolated authentication-migration identifier reported by
  Bandit;
- incomplete Compose cleanup for the documentation profile;
- missing `GCP_*` and `TF_VAR_*` environment sanitization;
- unbounded command-start failures in the root orchestrator.

Review pass 2 repeated the complete local gate and the final focused gate.
There are no unresolved local findings. The complete run passed in 485.2
seconds; the final focused rerun passed in 39.2 seconds.

## 9. Definition Of Done

- [x] One documented command runs the complete no-apply drift gate.
- [x] One synchronized verification matrix supplies independent hard expected
      values to all project tests.
- [x] Representative complete paths and all 27 storage triples pass.
- [x] Azure F1/S1/S2/S3 formula-to-Terraform continuity passes.
- [x] Standard/mover runtimes, AWS Deep Archive, GCP Archive, transition
      ownership, and glue ownership have hard assertions.
- [x] Every canonical negative fails before executable side effects.
- [x] Every deployable registry target has a variable, validation, and
      Terraform consumer; evidence-only dimensions have none.
- [x] Optimizer, Management, Deployer, Flutter, Terraform, docs, Compose,
      static, and security gates pass without cloud credentials.
- [ ] Existing CI proves native macOS, Windows, and Linux release builds after
      the branch is pushed.
- [x] Two independent review passes have no unresolved local findings.
- [ ] Documentation and GitHub issues match the implementation after push.
- [ ] #128 is closed with commit and verification evidence.
- [ ] Parent #118 is updated; closure waits for the user's requested later
      application finalization/E2E decision.
- [ ] Only then may repository architecture Phase 8 implementation begin.
