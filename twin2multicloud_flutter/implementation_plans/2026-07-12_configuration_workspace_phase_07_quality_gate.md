# Configuration Workspace Phase 7: Quality And Migration Gate

## Objective

Close the migration with no live legacy navigation, consistent domain language,
responsive verification, full static/test/build evidence, documentation status,
and issue traceability.

## Gate

- Remove the unreferenced three-step indicator and its legacy-only tests.
- Replace visible Step 1/2/3 instructions with workspace task language.
- Preserve historical planning documents but mark the new roadmap authoritative.
- Run analyzer, full tests, web build, and macOS build.
- Inspect touched code for secret rendering, direct Optimizer/Deployer calls,
  duplicate readiness logic, unreachable tasks, and overflow risks.
- Update GitHub #38 with commits and verification. Keep #39 open unless the
  complete deployment lifecycle, including operations, is finished.

## Acceptance

- The production UI contains no fixed three-step navigation.
- Every approved task has a focused content owner.
- Read-only, error, blocked, invalidated, not-required, wide, and compact states
  are represented.
- All quality commands pass or an external tool warning is documented.

