# AI-Assisted Pricing Candidate Review

## Metadata

- Status: planned
- Scope owner: `2-twin2clouds`
- Related roadmap: `docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`
- Depends on:
  - pricing registry SSOT
  - pricing model/source classifications
  - provider pricing contracts
  - deterministic candidate matching
  - intent-to-result traceability
- No live deployment E2E in this phase
- No AI dependency in runtime cost calculation
- AI review must be optional because OpenAI API usage is metered and billed
  separately from ChatGPT subscriptions. As of 2026-06-13, this plan assumes no
  reliable free API tier for production or thesis verification.

## Goal

Add an optional AI-assisted review workflow for pricing API candidate rows.

The system should combine deterministic contract logic with semantic AI review
in a way that improves developer/user diagnostics without making AI the source
of truth for publishable pricing.

## AI Availability And Configuration

AI review is an optional server-side capability. The application must remain
fully usable when no AI provider is configured.

Configuration contract:

- `AI_REVIEW_ENABLED=false` by default
- `AI_REVIEW_PROVIDER=openai`
- `OPENAI_API_KEY` provided only to the Optimizer container or its secret store
- `AI_REVIEW_MODEL` pinned to a configured model, not hard-coded in handlers
- `AI_REVIEW_TIMEOUT_SECONDS` with a conservative default
- `AI_REVIEW_MAX_CANDIDATES` to bound prompt size and cost
- `AI_REVIEW_MAX_INPUT_TOKENS` and `AI_REVIEW_MAX_OUTPUT_TOKENS` to enforce
  cost controls

Startup behavior:

- if `AI_REVIEW_ENABLED=false`, AI review is disabled and candidate review still
  works with deterministic evidence
- if `AI_REVIEW_ENABLED=true` but `OPENAI_API_KEY` is missing, startup must not
  fail; the AI capability is reported as disabled with reason `missing_api_key`
- if the OpenAI request fails, times out, is rate-limited, or returns malformed
  output, the candidate review payload returns `ai_review_failed`; deterministic
  candidates remain visible and selectable according to contract gates
- Flutter must never receive the OpenAI key, model credentials, provider
  credentials, local file paths, or raw unsanitized provider payloads

Docker/operations contract:

- local compose files may pass `OPENAI_API_KEY` from the host environment or a
  Docker secret
- no API key may be committed to the repository or copied into Flutter config
- the Management API exposes only AI capability state, such as `enabled`,
  `disabled_reason`, and `last_error_category`
- the Optimizer owns all AI prompt construction and sanitization

Credential ownership decision:

- the OpenAI API key is an operator/platform secret, comparable to database
  passwords, signing keys, or payment provider API keys
- it must not be managed like user/twin cloud admin credentials in Flutter
- Flutter may show read-only AI capability diagnostics but must not upload,
  store, rotate, reveal, or validate the OpenAI API key
- user/twin cloud admin credentials remain a separate domain workflow because
  they bootstrap least-privilege cloud credentials for a specific twin
- bring-your-own-AI-key per user/project is a future product feature only; it
  would require encrypted secret storage, RBAC, audit logs, rotation, budget
  limits, and explicit abuse/cost controls before being allowed

## Core Decision

AI may recommend and explain a candidate, but it must not directly make a
publishable pricing decision.

Publishable pricing remains allowed only when:

- deterministic contract validation passes
- unit, tier, currency, region, source type, and normalization are compatible
- an ambiguous or AI-disagreement case has an explicit reviewed decision
- the selected row is persisted through the review/registry decision path

## Unified Review Flow

```text
provider pricing API rows
    -> provider-specific parser
    -> deterministic hard filters
    -> deterministic candidate scoring
    -> optional AI semantic review over bounded candidate set
    -> compare deterministic result with AI suggestion
    -> user/dev review when ambiguous or disagreement exists
    -> selected row is contract-validated
    -> reviewed decision is persisted
    -> publishable mapping only if validation passes
```

## Decision Cases

### Case 1: Deterministic Logic And AI Agree

If deterministic logic selects exactly one candidate and AI selects the same
candidate:

- status may remain `publishable` if all contract gates pass
- UI may show `Contract logic and AI review agree`
- trace stores AI agreement as diagnostic metadata only
- no human review is required

### Case 2: Deterministic Logic Is Ambiguous

If deterministic logic returns multiple plausible candidates:

- status becomes `review_required`
- UI shows deterministic candidates, scores, pass/fail checks, and rejected
  alternatives
- AI may suggest one candidate with rationale
- user/dev may choose:
  - deterministic top candidate
  - AI-suggested candidate
  - another visible candidate
  - no candidate / unresolved
- selected candidate must pass contract validation before becoming publishable

### Case 3: Deterministic Logic And AI Disagree

If deterministic logic selects candidate A and AI suggests candidate B:

- status becomes `review_required`
- UI shows both A and B prominently
- UI also shows close alternatives when available
- user/dev may choose A, B, another row, or unresolved
- selected candidate must pass contract validation before becoming publishable

## Contract Boundaries

This track has three explicit contract boundaries. They must be implemented in
this order so UI and Management API work do not invent their own pricing truth.

### Optimizer Contract

The Optimizer owns provider candidate generation and semantic review payloads.

Stable Optimizer DTOs:

- `PricingCandidateReport`
- `PricingCandidate`
- `PricingCandidateContractCheck`
- `AISemanticReviewRequest`
- `AISemanticReviewResult`
- `PricingCandidateReviewResolution`
- `ReviewedPricingDecision`

The Optimizer must expose read-only candidate review output and a validated
resolution command. It must not expose raw provider credentials, raw auth
errors, or unbounded provider API rows.

### Management API Contract

The Management API owns user/twin-scoped persistence and authorization.

Responsibilities:

- store reviewed candidate decisions with user/twin/project context
- enforce ownership and role checks for review decisions
- keep an audit trail for who selected which row and why
- pass approved decisions back to Optimizer during pricing refresh/review flows
- expose review state to Flutter through stable API schemas

Non-responsibilities:

- no provider row matching logic
- no AI prompt construction
- no pricing truth outside reviewed decision metadata

### Flutter UI Contract

Flutter owns the review workflow presentation.

Responsibilities:

- show deterministic candidates, AI suggestion, and close alternatives
- show agreement/ambiguity/disagreement status
- show hard contract gate pass/fail state
- let the user choose A, B, another candidate, or unresolved
- prevent approval when the backend says the selected row fails hard validation
- show the AI capability state without blocking deterministic review
- render the same candidate table whether AI is enabled or disabled

Non-responsibilities:

- no AI key handling
- no provider credentials
- no local pricing validation beyond displaying backend results
- no direct write to Optimizer registry files

## API Contract Sketch

The exact routes may be adjusted to existing route conventions, but these
contract shapes are required.

### Optimizer Read Contract

```http
GET /pricing-review/candidates/{provider}/{intent_id}
```

Returns:

```json
{
  "schema_version": "pricing-candidate-report.v1",
  "provider": "azure",
  "intent_id": "iot.message_ingest",
  "status": "review_required",
  "deterministic_selection": {
    "candidate_id": "azure.iot.message_ingest.meter-123",
    "status": "ambiguous",
    "score": 0.91
  },
  "ai_review": {
    "status": "not_requested",
    "suggested_candidate_id": null
  },
  "ai_capability": {
    "enabled": false,
    "provider": "openai",
    "disabled_reason": "missing_api_key"
  },
  "candidates": [],
  "contract_validation": {}
}
```

### Optimizer AI Review Contract

```http
POST /pricing-review/candidates/{provider}/{intent_id}/ai-review
```

Input must contain only sanitized candidate summaries and the relevant contract
metadata. The server may also construct this input internally to avoid trusting
client-provided prompt material.

Returns an `AISemanticReviewResult`. This result is advisory and cannot mark a
field publishable.

### Management API Review Decision Contract

```http
POST /twins/{twin_id}/pricing-review/decisions
```

Request:

```json
{
  "provider": "azure",
  "intent_id": "iot.message_ingest",
  "candidate_report_id": "report-123",
  "selected_candidate_id": "candidate-456",
  "basis": "ai_disagreement",
  "notes": "Selected AI suggestion after checking meter unit and tier."
}
```

Response:

```json
{
  "review_decision_id": "decision-789",
  "status": "accepted",
  "contract_validation_status": "passed",
  "publishability_status": "publishable",
  "audit": {
    "reviewed_by": "user-id",
    "reviewed_at": "2026-06-13T00:00:00Z"
  }
}
```

### Flutter Review View Contract

Flutter consumes Management API responses, not Optimizer internals directly.

Minimum UI states:

- `agreed_publishable`
- `review_required_ambiguous`
- `review_required_ai_disagreement`
- `blocked_contract_validation_failed`
- `unresolved`
- `ai_disabled`
- `ai_review_failed`

Detailed UI plan:

- Entry point: pricing refresh/configuration surfaces show a review indicator
  when a provider/intent has `review_required`, `ai_review_failed`, or
  `blocked_contract_validation_failed`.
- Main layout: one review view grouped by provider and intent. Each group shows
  current publishability state, deterministic selection, AI capability state,
  and required user action.
- Recommendation area: two compact comparison panels show `Contract logic` and
  `AI semantic review`. When AI is disabled, the AI panel shows disabled state
  and reason, not an empty/error-looking card.
- Candidate table: visible for every state and includes candidate id, service,
  meter/SKU id, unit, tier, currency, region, source type, normalized price,
  deterministic score, contract gate status, and selectable/blocked state.
- Candidate detail drawer: shows sanitized provider summary, matched intent,
  hard gate results, rejected/accepted rationale, normalization rule, source
  fingerprint, and stale/fresh evidence state.
- Actions: `Approve selected row`, `Mark unresolved`, `Request AI review`
  when AI is enabled, `Refresh candidates`, and `Open evidence details`.
- Approval behavior: approval is enabled only for backend-selectable candidates
  whose hard contract validation passes. AI suggestions do not override this.
- Disabled AI behavior: the user can still inspect all candidates, approve a
  contract-valid row, or mark unresolved. The UI may show guidance that AI can
  be enabled server-side by configuring the Optimizer, but it must not ask the
  user for an API key in Flutter.
- Copy constraints: avoid "AI verified". Use "AI semantic review agrees",
  "AI suggests a different candidate", "AI review disabled", or "Manual review
  required".

ASCII layout sketch:

```text
Pricing Review
|-- Provider / Intent List
|   |-- azure / iot.message_ingest      review_required
|   |-- gcp / pubsub.message_ingest     agreed_publishable
|   `-- aws / storage.gb_month          ai_disabled
`-- Review Detail
    |-- Status + Publishability Gates
    |-- Contract Logic Recommendation
    |-- AI Semantic Review Recommendation / Disabled State
    |-- Candidate Table
    |-- Candidate Evidence Drawer
    `-- Actions: Approve | Mark unresolved | Refresh | Request AI review
```

## Target Data Model

### Candidate Record

Each provider API row that survives parsing should become a bounded candidate
record:

- `candidate_id`
- `provider`
- `intent_id`
- `service`
- `region`
- `currency`
- `unit`
- `tier`
- `sku_or_meter_id`
- `product_family`
- `pricing_model_hints`
- `source_type`
- `raw_row_fingerprint`
- `sanitized_summary`
- `contract_check_results`
- `deterministic_score`
- `deterministic_rank`
- `rejection_reasons`
- `ui_summary`
- `is_selectable`
- `blocking_validation_errors`

Raw provider payloads must not be stored unbounded in publishable outputs.

### AI Review Record

AI review output is diagnostic metadata:

- `ai_review_id`
- `model`
- `prompt_version`
- `candidate_ids`
- `suggested_candidate_id`
- `confidence`
- `rationale`
- `rejected_candidate_rationales`
- `missing_information`
- `requires_human_review`
- `created_at`

AI review must not contain credentials, raw provider auth errors, or local file
paths.

### Reviewed Decision

Human/user-approved decision:

- `review_decision_id`
- `provider`
- `intent_id`
- `selected_candidate_id`
- `decision_source`: `human_review`
- `basis`: `deterministic_agreement`, `ambiguous_selection`, `ai_disagreement`
- `reviewer`
- `reviewed_at`
- `contract_validation_status`
- `publishability_status`
- `notes`
- `candidate_report_id`
- `ai_review_id`
- `selected_row_fingerprint`
- `staleness_status`

Reviewed decisions become part of the auditable mapping/evidence workflow.
They are persisted in the Management API database. Flutter must never write
directly into source-controlled registry files. Registry files remain the source
of truth for pricing contracts, mappings, classifications, and formula
compatibility; reviewed decisions are user/twin-scoped evidence and audit state.

## Subphases

### Phase A: Candidate Contract And Deterministic Match Report

Goal: Make deterministic matching inspectable before adding AI.

Scope:

- define candidate record schema
- emit selected and rejected candidates from provider fetchers
- include deterministic hard-filter results and scores
- persist or expose candidate reports for UI/dev review
- ensure no raw credentials or unbounded provider payloads are exposed

Definition of Done:

- every candidate has a deterministic ID and sanitized summary
- every rejected alternative has a machine-readable rejection reason
- ambiguous matches become `review_required`
- tests cover exact match, ambiguous match, no match, and rejected candidates
- candidate report schema is versioned and snapshot-tested
- no Flutter or Management API work depends on raw provider payloads

Implementation readiness: ready.

Enterprise/thesis review:

- Clear boundary: Optimizer-only.
- Data contract: candidate report schema required.
- Testability: deterministic fixture-based tests.
- Risk: provider-specific parsers may need real sampled rows; use sanitized
  fixtures checked into tests.

### Phase B: AI Semantic Review Adapter

Goal: Add optional AI review over a bounded candidate set.

Scope:

- introduce an AI review interface independent of one vendor
- implement a disabled-by-default OpenAI adapter, with a local fake adapter only
  for unit/integration tests
- send only sanitized candidate summaries and the pricing intent contract
- require prompt versioning and deterministic JSON response schema
- treat AI output as diagnostic suggestion only
- implement an `AIReviewCapability` service that reports enabled/disabled
  state and reason without requiring Flutter to know provider internals

Definition of Done:

- AI review is never called by normal `/calculate`
- AI review is optional for pricing refresh/review flows
- AI review output is schema-validated
- tests cover malformed AI output, missing suggestion, and disagreement
- AI adapter is feature-flagged and can be disabled without breaking refresh
- missing `OPENAI_API_KEY` produces `ai_disabled` capability metadata, not a
  runtime crash
- configured `OPENAI_API_KEY` stays server-side in environment variables or
  secret management
- tests cover disabled-by-default, enabled-with-missing-key, timeout,
  rate-limit/error classification, and malformed output
- AI request/response schemas are versioned
- no AI key is ever sent to Flutter or Management API clients

Implementation readiness: ready.

Adapter decision:

- implement a provider-neutral AI review interface first
- add OpenAI as the first concrete adapter
- keep the adapter disabled by default unless `AI_REVIEW_ENABLED=true` and
  `OPENAI_API_KEY` is present

Enterprise/thesis review:

- Clear boundary: advisory only.
- Security: sanitized bounded input only.
- Testability: fake adapter for unit/integration tests.
- Risk: live AI calls are nondeterministic; production tests must mock them.

### Phase C: Agreement And Disagreement Resolver

Goal: Compare deterministic result with AI suggestion and produce a review
status.

Scope:

- classify cases as `agreed`, `ambiguous`, `disagreement`, `unresolved`
- if agreed and contract gates pass, allow publishable status
- if ambiguous or disagreement, require explicit user/dev selection
- expose selected/rejected candidates and AI suggestion in one review payload

Definition of Done:

- case 1 shows deterministic/AI agreement
- cases 2 and 3 both become `review_required`
- user selection is required before publishability when ambiguous/disagreed
- tests cover A/B selection, unresolved decision, and invalid selected row
- resolver output includes UI state and allowed user actions
- selected candidate is re-run through contract validation before acceptance

Implementation readiness: ready.

Enterprise/thesis review:

- Clear boundary: pure domain service, no HTTP or AI call required.
- Data contract: resolver payload drives UI and Management API.
- Testability: table-driven tests for all decision cases.
- Risk: avoid confidence thresholds as hidden publishability logic.

### Phase D: Review Decision Persistence

Goal: Store user-approved row choices as audit records.

Scope:

- persist reviewed decisions in the Management API database with user/twin
  ownership context
- link decision to candidate report, AI review, and contract validation result
- allow future pricing refreshes to reuse reviewed decisions when fingerprints
  still match
- mark decisions stale when provider rows drift
- expose a typed Management API client call to Optimizer when reviewed decisions
  should influence refresh/review behavior

Definition of Done:

- reviewed decisions are reproducible and auditable
- stale decisions cannot silently remain publishable
- tests cover decision reuse, stale fingerprint, and contract failure after
  manual selection
- database migration exists for reviewed pricing decisions
- API authorization verifies current user owns the twin/project
- Management API tests cover create/list/detail and stale decision behavior

Implementation readiness: ready.

Enterprise/thesis review:

- Clear boundary: Management API owns user-scoped decisions.
- Data contract: reviewed decision schema required.
- Testability: DB migration + route/service tests.
- Risk: do not write directly into source-controlled registry files from the UI.

### Phase E: Read-Only Review API And UI Workflow

Goal: Support the UI flow without making pricing editable in unsafe places.

Scope:

- Optimizer endpoint for candidate reports
- Optimizer endpoint/action to request optional AI review
- Management API endpoint/action to submit reviewed candidate selection
- Management API endpoint to expose current review status to Flutter
- Flutter review screen or panel in the pricing refresh/configuration workflow
- UI shows:
  - deterministic selection
  - AI suggestion
  - AI enabled/disabled state
  - all close candidates
  - pass/fail contract checks
  - selected/rejected rationale
  - publishability status

Definition of Done:

- user can resolve ambiguous/disagreement cases
- UI cannot approve a row that fails hard contract validation
- all actions produce audit records
- no AI key or provider credential is exposed to Flutter
- generated/typed client contract is updated if the project uses generated API
  clients
- UI has loading, empty, error, ai-disabled, and validation-blocked states
- AI-disabled state still shows deterministic candidates and selectable
  contract-valid rows
- UI copy is concise and avoids implying AI is authoritative
- AI-suggested candidate may be preselected as a draft UI selection, but it is
  not accepted or publishable until the user explicitly approves and backend
  contract validation passes

Implementation readiness: mostly ready, but should be split into two
implementation slices.

Recommended split:

- Phase E1: backend APIs and schemas
- Phase E2: Flutter UI workflow

Enterprise/thesis review:

- Clear boundary: UI consumes Management API; Optimizer remains backend-only
  for candidate/AI internals.
- Data contract: explicit UI state enum.
- Testability: backend route tests, Flutter widget tests, golden/screenshot
  smoke if applicable.
- Risk: avoid turning this into a full pricing registry editor.

### Phase F: Thesis And Operations Guardrails

Goal: Make the approach explainable and operationally safe.

Scope:

- document why AI is advisory, not SSOT
- document that OpenAI API usage is metered and must not be assumed free
- document failure modes and publishability guarantees
- add cost/rate-limit controls for AI calls
- add config flag to disable AI review entirely
- document Docker/env setup:
  - `AI_REVIEW_ENABLED`
  - `AI_REVIEW_PROVIDER`
  - `OPENAI_API_KEY`
  - `AI_REVIEW_MODEL`
  - token/candidate/time limits
- add thesis examples for agreement, ambiguity, and disagreement

Definition of Done:

- AI review is off by default in local/dev unless configured
- runtime calculation works without AI credentials
- UI review workflow works without AI credentials
- docs include a reproducible trace from candidate rows to reviewed decision
- thesis reasoning document explains deterministic vs AI-assisted decision
  ownership
- operations documentation covers AI cost/rate limits and failure behavior
- feature flag and missing-key behavior are tested

Implementation readiness: ready.

Enterprise/thesis review:

- Clear boundary: docs/config/tests only.
- Data contract: feature flag and operational behavior.
- Testability: config tests and docs review.
- Risk: do not overstate AI correctness; document it as a reviewer.

## Phase Review Summary

| Phase | Implementation-ready? | Enterprise-grade? | Thesis-ready? | Required follow-up |
|---|---|---|---|---|
| A Candidate Contract | Yes | Yes | Yes | Add sanitized provider fixtures. |
| B AI Review Adapter | Yes | Yes | Yes | Provider-neutral interface, OpenAI first adapter, disabled by default. |
| C Resolver | Yes | Yes | Yes | Keep pure/domain-level. |
| D Persistence | Yes | Yes | Yes | Implement in Management API DB, not registry writes. |
| E API + UI | Backend yes; UI should split | Yes if split | Yes | Split into E1 backend and E2 Flutter. |
| F Guardrails | Yes | Yes | Yes | Add feature-flag and thesis docs. |

Overall review result: implementation-ready after splitting Phase E into backend
and Flutter slices. The target architecture is enterprise-grade because AI is
advisory, all publishable decisions remain contract-validated, and user
selection is audited. It is thesis-ready because it produces explainable
agreement/ambiguity/disagreement cases without relying on opaque AI decisions
for final cost truth.

## Non-Goals

- No AI call during normal `/calculate`
- No automatic publishable decision based only on AI
- No raw provider payload upload to AI
- No credential upload to AI
- No pricing registry editor in this phase unless explicitly planned later
- No live cloud deployment E2E

## Security Requirements

- AI input must be sanitized and bounded.
- AI output must be treated as untrusted input and schema-validated.
- Provider credentials and local credential paths must never be sent to AI.
- Review decisions must be auditable.
- All publishable paths must still pass deterministic contract validation.

## Recommended Implementation Order

1. Finish deterministic candidate reports and traceability.
2. Implement candidate review payloads without AI.
3. Add optional AI semantic review behind a feature flag.
4. Add resolver logic for agreement/ambiguity/disagreement.
5. Add reviewed decision persistence.
6. Add UI workflow.
7. Add thesis documentation and examples.

## Testing Strategy

Unit tests:

- candidate parsing and scoring
- AI output schema validation
- agreement/disagreement resolution
- reviewed decision validation
- stale fingerprint detection
- secret redaction

Integration tests:

- provider refresh creates candidate report
- ambiguous candidate report blocks publishability
- AI suggestion is displayed but does not auto-publish
- user-selected row passes/fails contract validation deterministically

Snapshot tests:

- candidate report shape
- AI review payload shape
- reviewed decision shape

## Decisions

- Reviewed decisions live in the Management API database. Registry files remain
  the source of truth for contracts/mappings/classifications; UI does not write
  registry files.
- AI review is an authenticated user/twin-scoped capability for now. No
  role/admin gating is planned until the platform has a real RBAC model.
- Which provider rows should be sent to AI: top 5, top 10, or all candidates
  after hard filters?
- AI confidence is diagnostic metadata only. It may explain why a candidate was
  suggested or preselected, but must not become publishability logic.
