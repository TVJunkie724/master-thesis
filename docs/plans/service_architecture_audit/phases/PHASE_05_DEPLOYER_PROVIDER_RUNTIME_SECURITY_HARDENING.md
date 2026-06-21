---
title: "Phase 5: Deployer Provider Runtime Security Hardening"
description: "Resolve the Deployer provider-runtime Bandit residuals with explicit runtime boundaries, narrow suppressions, and reproducible safe verification."
tags: [deployer, security, provider-runtime, bandit, thesis]
lastUpdated: "2026-06-21"
version: "1.1"
githubIssue: "#106"
status: "Complete"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md
- docs/plans/service_architecture_audit/phases/PHASE_04_SERVICE_QUALITY_GATE.md
- 3-cloud-deployer/src/api/simulator.py
- 3-cloud-deployer/src/api/verify.py
- 3-cloud-deployer/src/terraform_runner.py
- 3-cloud-deployer/src/validation/core.py
- 3-cloud-deployer/src/validator.py
- 3-cloud-deployer/src/providers/
- 3-cloud-deployer/tests/
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Phase 5: Deployer Provider Runtime Security Hardening

## Summary

Harden the remaining Deployer static-security findings that were documented as
residual risk after the service quality gate. This phase focuses on provider
runtime code packaged into AWS Lambda, Azure Functions, and GCP Cloud Functions,
plus the local Terraform/simulator process boundaries that Bandit still reports
in a full `/app/src` scan.

The target state is not a cosmetic Bandit suppression pass. Every remaining
finding must be either fixed by a stronger boundary or accepted with a narrow
line-level `# nosec` marker and a code-adjacent rationale that explains why the
runtime behavior is safe.

## Scope

| In scope | Out of scope |
|---|---|
| Provider runtime `urlopen` calls and URL scheme validation | Live cloud E2E execution |
| Silent exception handling in packaged runtime helpers | Replacing provider HTTP architecture |
| Terraform and simulator subprocess boundaries | Replacing Terraform |
| Bandit false positives for verification counters and parameterized queries | Reworking simulator UX |
| Safe unit/integration/API tests plus Bandit full-source gate | Cloud account least-privilege validation |

## Findings To Resolve

| Finding family | Current signal | Required disposition |
|---|---|---|
| `B310` runtime `urlopen` | Provider functions open dynamically configured URLs. | Add HTTPS-only validation before outbound calls; keep `urlopen` as standard-library runtime dependency; mark only the validated call lines with `# nosec B310`. |
| `B110` silent `except/pass` | Error-body parsing and partial JSON context loading silently swallow failures. | Replace silent `pass` with typed fallbacks or debug diagnostics; never hide control-flow failures. |
| `B404/B603` subprocess | Simulator and Terraform runner execute local CLI commands. | Validate executable/script boundaries; preserve `shell=False`; use narrow `# nosec` only on controlled process launch lines. |
| `B105` verification counters | `"pass"` and `"pass_count"` are classified as possible hardcoded passwords. | Mark the exact counter literals as false positives with `# nosec B105`; do not suppress the file. |
| `B608` Cosmos query | Parameterized Azure Cosmos query string is flagged as possible SQL injection. | Verify query parameters are used; mark the exact query string with `# nosec B608` and keep the parameter list adjacent. |
| Broad/bare exception handling | Validation fallbacks and retry helpers catch too broadly. | Narrow exceptions where the expected failure mode is known; keep broad catches only where the runtime boundary truly requires retry/error propagation. |

## Implementation Plan

1. Add provider-runtime URL validation helpers.
   - Require `https://` for remote inter-cloud and Azure function URLs.
   - Reject missing hosts.
   - Preserve existing request payloads, auth headers, and retry behavior.
   - Avoid new third-party dependencies because the files are packaged into
     cloud runtimes.

2. Harden provider-runtime error handling.
   - Replace `except Exception: pass` while reading HTTP error bodies with a
     deterministic placeholder.
   - Keep diagnostics user-safe and avoid logging tokens or full credential
     payloads.
   - Narrow JSON parsing fallbacks in validation modules to JSON/type/value
     errors.

3. Harden local process boundaries.
   - Validate simulator script paths stay under the canonical simulator source
     tree before launching.
   - Validate Terraform command arguments are a non-empty list of strings and
     continue to execute with `shell=False`.
   - Keep process invocations line-level documented for Bandit.

4. Document unavoidable static-analysis false positives.
   - Mark verification status counters and parameterized Cosmos query lines
     only where reviewed.
   - No file-level or broad test-level suppressions.

5. Add/adjust tests.
   - Cover HTTPS validation success/failure for shared provider runtime helpers.
   - Cover simulator path validation for controlled scripts.
   - Preserve existing Terraform runner behavior with command validation.
   - Keep live cloud E2E tests opt-in and out of default verification.

6. Execute two review loops before commit.
   - Review 1 checks implementation behavior, test coverage, and static
     security output; all findings must be fixed before the second review.
   - Review 2 repeats the security/test gates and performs a final nosec/path
     suppression audit; all findings must be fixed before committing.

## Acceptance Criteria

- A full Deployer Bandit scan over `/app/src` passes without unreviewed Medium
  or Low findings.
- Every remaining `# nosec` is line-specific and tied to a controlled boundary
  or a documented false positive.
- Provider runtime outbound HTTP calls reject non-HTTPS targets before
  `urlopen` is reached.
- Simulator and Terraform process launches still work through controlled local
  commands and never use shell execution.
- Existing safe Deployer tests continue to pass.
- The implementation does not require live cloud credentials or paid E2E runs.

## Verification Gates

Run from the repository root through the Deployer Docker image:

```bash
docker run --rm \
  -v "$PWD/3-cloud-deployer:/app" \
  -w /app \
  -e PYTHONPATH=/app \
  3cloud-deployer:latest \
  python -m pytest tests/unit tests/api tests/integration tests/test_gcp_simulator.py -q
```

```bash
docker run --rm \
  -v "$PWD/3-cloud-deployer:/app" \
  -w /app \
  -e PYTHONPATH=/app \
  3cloud-deployer:latest \
  python -m bandit -q -r /app/src
```

## Review Checklist

- No unvalidated `urlopen` call remains in `3-cloud-deployer/src/providers`.
- No silent `except: pass` or `except Exception: pass` remains in touched source
  files.
- No generic file-level Bandit suppression was introduced.
- Tests prove both positive and negative paths for new runtime validation.
- Two review rounds are completed and their findings are fixed before commit.
- The roadmap and GitHub issue `#106` can be updated with concrete evidence.

## Implementation Evidence

Status: Complete on 2026-06-21.

Implemented hardening:

- Provider runtime outbound HTTP calls now validate absolute HTTPS URLs before
  reaching `urlopen`.
- Shared AWS, Azure, and GCP inter-cloud helpers reject `http://`, missing-host,
  empty, and non-string URLs before network access.
- Runtime HTTP error-body parsing no longer uses silent `except/pass`
  fallbacks.
- Simulator process launch resolves the provider entrypoint inside the
  canonical simulator source tree before `subprocess.Popen`.
- Terraform runner validates non-empty string argument lists before controlled
  `shell=False` execution.
- Verification counter false positives were refactored to avoid unnecessary
  Bandit suppressions.
- Azure Cosmos query construction remains parameterized and no longer requires
  a Bandit suppression.

Review 1 evidence:

- Targeted boundary tests: `48 passed`.
- Full Deployer Bandit scan: exit 0, no findings.
- Fixes applied after review: code-adjacent rationale comments for required
  `nosec` markers and broader HTTP error-body fallback handling.

Review 2 evidence:

- Safe Deployer suite: `1073 passed, 1 skipped, 1 warning`.
- Full Deployer Bandit scan: exit 0, no findings and no warning output.
- Final manual audit: `urlopen`, subprocess, `# nosec`, and broad-exception
  search reviewed against the phase scope.

## Roadmap Anchor

[Service Architecture Audit Roadmap](../ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md)
