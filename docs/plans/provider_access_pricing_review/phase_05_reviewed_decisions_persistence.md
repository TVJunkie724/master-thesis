# Phase 5: Reviewed Decisions Persistence

**Status:** planned
**Primary owner:** Management API
**Depends on:** Pricing candidate reports and Phase 1 credential purpose model

## Goal

Persist user-reviewed pricing candidate decisions in the Management API database
with audit metadata and stale-detection.

This phase must be completed before the Pricing Review Center enables
`Approve Selection`, because UI approval requires a durable backend contract.

## Data Model

`pricing_review_decisions`:

| Field | Purpose |
|---|---|
| `id` | Decision id |
| `user_id` | Owner/reviewer |
| `provider` | AWS/Azure/GCP |
| `intent_id` | Pricing intent |
| `selected_candidate_id` | Chosen candidate |
| `candidate_report_id` | Source report |
| `ai_review_id` | Optional AI metadata |
| `pricing_connection_id` | Credential used during fetch |
| `selected_row_fingerprint` | Drift detection |
| `basis` | deterministic agreement, ambiguous selection, AI disagreement |
| `status` | accepted, unresolved, stale, invalid |
| `notes` | Optional user note |
| `created_at` / `updated_at` | Audit timestamps |

## API Contract

```http
POST /optimizer/pricing-review/decisions
GET /optimizer/pricing-review/decisions
GET /optimizer/pricing-review/decisions/{decision_id}
```

Approval request:

```json
{
  "provider": "aws",
  "intent_id": "iot.message_ingest",
  "candidate_report_id": "report-123",
  "selected_candidate_id": "candidate-456",
  "pricing_connection_id": "cc-aws-pricing",
  "basis": "ai_disagreement",
  "notes": "Selected after checking unit and tier."
}
```

## Rules

- Backend revalidates selected candidate contract gates before accepting.
- Stale fingerprints cannot silently remain publishable.
- Flutter cannot write source-controlled registry files.
- Unresolved decisions are first-class outcomes, not errors.

## Verification

- Migration tests.
- Service tests for approve/unresolved/stale/invalid candidate.
- Route tests for ownership and redaction.
- Integration tests with fake candidate reports.

## Definition Of Done

- [ ] Decisions are persisted in Management API DB.
- [ ] Decisions are user-owned and auditable.
- [ ] Contract validation is re-run on approval.
- [ ] Stale fingerprints block silent reuse.
- [ ] Registry files are not written by UI/API decision flows.
- [ ] Tests cover acceptance, unresolved, stale, invalid, and ownership.
