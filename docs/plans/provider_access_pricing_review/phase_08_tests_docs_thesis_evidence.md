# Phase 8: Tests, Docs, And Thesis Evidence

**Status:** planned
**Primary owner:** cross-project
**Depends on:** Phases 1-7

## Goal

Turn the provider access and pricing review workflow into verifiable
thesis-ready evidence.

## Required Verification Gates

Backend:

- Management API migration tests.
- Cloud access inventory tests.
- Pricing credential validation tests.
- Reviewed decision persistence tests.
- Secret redaction tests.
- No live cloud E2E in default CI/local gate.

Optimizer:

- Candidate report fixture tests.
- AI disabled/enabled adapter tests using fake adapter.
- Contract validation tests.
- Traceability snapshot tests.

Flutter:

- Dashboard Pricing Data Health widget tests.
- Profile Cloud Accounts & Access widget tests.
- Pricing Review Center BLoC and widget tests.
- Step 2 cleanup regression tests.
- Integration tests against running Management API.

Commands:

```bash
docker compose run --rm management-api sh -lc 'cd /app && PYTHONPATH=/app pytest tests -q'
docker compose run --rm optimizer sh -lc 'cd /app && PYTHONPATH=/app pytest tests -q'
cd twin2multicloud_flutter && flutter analyze
cd twin2multicloud_flutter && flutter test
cd twin2multicloud_flutter && flutter build web
```

## Required Documentation

- Credential lifecycle diagram.
- Provider access inventory explanation.
- Pricing refresh workflow.
- Reviewed decision persistence model.
- Why admin credentials are ephemeral.
- Why pricing credentials are user-scoped.
- Why AI is advisory and optional.
- Thesis example: deterministic agreement.
- Thesis example: deterministic ambiguity.
- Thesis example: AI disagreement.

## Definition Of Done

- [ ] All phase-specific tests pass.
- [ ] Docs describe final state, not legacy behavior.
- [ ] Thesis reasoning documents the architectural tradeoffs.
- [ ] Screens/workflows have ASCII diagrams.
- [ ] Verification commands are reproducible.
- [ ] No real cloud E2E is part of the default gate.
