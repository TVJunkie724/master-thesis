# AI-Assisted Pricing Candidate Review Reasoning

## Purpose

This document captures the reasoning behind the planned AI-assisted pricing
candidate review workflow. It is intended as thesis material and as an
implementation handoff for future development.

## Problem

Cloud provider pricing APIs return rows whose textual descriptions, units,
tiers, meter names, SKU names, regions, and billing modes differ between
providers and may drift over time.

Pure keyword matching is brittle because:

- provider wording changes without notice
- semantically similar rows may represent different billing intentions
- one service can expose multiple tiers, meters, and usage dimensions
- normalized cost comparison requires unit, tier, currency, and source
  compatibility, not only string similarity
- a wrong row may still look plausible in logs and UI

At the same time, allowing an AI system to directly select publishable pricing
truth would make the result difficult to audit and reproduce.

## Design Decision

AI is allowed to act as a semantic reviewer, but not as the source of truth.

The final publishable pricing decision is owned by deterministic contracts and,
when required, an explicit reviewed user/developer decision.

```text
provider API rows
    -> deterministic contract filters
    -> deterministic candidate scoring
    -> optional AI semantic review
    -> agreement / ambiguity / disagreement classification
    -> user/developer selection when needed
    -> contract validation
    -> reviewed decision persistence
    -> publishable only if deterministic gates pass
```

## Operational Constraint: AI Is Optional

OpenAI API usage must be treated as metered and paid API usage, not as a
guaranteed free project dependency. ChatGPT Free access is a separate product
surface and must not be assumed to include API access for this application.

Therefore the pricing review workflow must work in two modes:

- AI disabled: deterministic candidate reports, contract gates, alternatives,
  and manual review remain fully available.
- AI enabled: the Optimizer container receives an API key through server-side
  environment variables or secret management and can request a bounded semantic
  review over sanitized candidate summaries.

If the API key is missing, invalid, rate-limited, or unavailable, the system
must degrade to deterministic review instead of blocking price refresh or cost
calculation.

The OpenAI API key is intentionally not treated like cloud admin credentials.
Cloud admin credentials belong to the user/twin onboarding workflow and are
used to bootstrap least-privilege cloud credentials for the digital twin. The
OpenAI key enables a platform capability and can create shared API cost, so it
belongs to operator-controlled server configuration or secret management.

Managing OpenAI keys in Flutter would turn this into a bring-your-own-AI-key
product feature. That is possible later, but only with encrypted secret storage,
RBAC, audit trails, rotation, budget limits, and explicit abuse controls. It is
not part of the thesis-ready target for this pricing review track.

## Why Not Let AI Decide Directly?

AI can interpret semantic similarity, but it cannot prove pricing correctness.

For this system, correctness means that the selected row is compatible with:

- business intent
- provider pricing contract
- pricing model classification
- price source classification
- region and currency
- unit and normalization rule
- tier semantics
- formula set
- publishability gates

These properties must be deterministic, testable, and auditable. A model answer
can be useful evidence for review, but it must not replace contract validation.

## Why Use AI At All?

AI may be useful where deterministic logic has already reduced provider rows to
a small candidate set, but the remaining rows differ mainly in wording or
provider-specific terminology.

Useful AI tasks:

- explain why candidate A or B appears semantically closer to an intent
- compare candidate descriptions against the intent and provider contract
- highlight missing information or suspicious wording
- help a user understand rejected alternatives
- act as a drift diagnostic when provider labels change

The AI review result is therefore diagnostic metadata, not pricing truth.

## Decision Cases

### Agreement

If deterministic logic finds one valid candidate and AI suggests the same
candidate, the UI may show that both systems agree.

This improves user confidence, but the row is publishable only because the
deterministic validation passed.

### Ambiguity

If deterministic logic finds multiple plausible candidates, the system marks
the field `review_required`.

The UI shows all close candidates and may show the AI suggestion. A user or
developer selects the final candidate or leaves the mapping unresolved.

### Disagreement

If deterministic logic selects candidate A and AI suggests candidate B, the
system also marks the field `review_required`.

The UI shows both A and B and lets the user choose A, B, another candidate, or
unresolved. The selected candidate must pass contract validation before it can
become publishable.

## Architecture Boundaries

### Optimizer

The Optimizer owns:

- provider candidate parsing
- deterministic candidate scoring
- candidate reports
- optional AI review adapter
- contract validation
- publishability state

The Optimizer does not own user authorization or long-term user-scoped review
history.

### Management API

The Management API owns:

- user/twin-scoped reviewed decisions
- authorization and ownership checks
- audit trail
- exposing review state to Flutter
- passing approved reviewed decisions back to the Optimizer during pricing
  refresh/review flows

It does not implement provider row matching or AI prompt construction.

### Flutter UI

Flutter owns:

- displaying deterministic candidates and AI suggestions
- showing agreement, ambiguity, disagreement, and validation-blocked states
- submitting the user's reviewed selection
- showing whether AI review is enabled, disabled, unavailable, or failed

Flutter must never receive AI keys or provider credentials.

## Source Of Truth

The source of truth remains deterministic and reviewable:

- provider pricing contracts define what is allowed
- pricing model/source classifications define expected source semantics
- candidate reports explain selected/rejected rows
- reviewed decisions store user/developer choices
- publishability gates determine whether a choice may contribute to trusted
  calculation output

AI review records are supporting evidence only.

## UI Implications

The UI should show enough context for informed review:

- deterministic selected candidate
- AI suggested candidate
- AI capability state and disabled reason
- close alternatives
- hard contract checks
- source type
- unit, tier, currency, region
- selected/rejected rationale
- publishability status

The UI should not say "AI verified this price." Better wording:

- "AI semantic review agrees with contract logic"
- "AI suggests a different candidate"
- "AI review disabled"
- "Manual review required"
- "Selection blocked by contract validation"

The candidate table remains the core UI element. AI is an additional evidence
panel, not a replacement for the deterministic table.

```text
Pricing Review
|-- Intent status and publishability gates
|-- Contract logic recommendation
|-- AI semantic review recommendation or disabled state
|-- Candidate table with all selectable/blocked rows
|-- Evidence drawer for sanitized provider details
`-- Actions: approve, mark unresolved, refresh, request AI review
```

## Enterprise-Grade Criteria

The design is enterprise-grade if:

- AI is disabled without breaking runtime calculation
- AI-disabled UI still allows deterministic/manual review
- all AI inputs are sanitized and bounded
- AI outputs are schema-validated as untrusted input
- user-selected rows are contract-validated
- reviewed decisions are audited
- stale provider fingerprints block silent reuse
- no credentials or local file paths are sent to AI or Flutter
- tests cover agreement, ambiguity, disagreement, stale decisions, malformed AI
  output, and blocked validation

## Thesis-Relevant Argument

The approach demonstrates a hybrid architecture:

- deterministic contracts provide reproducibility and auditability
- AI provides semantic assistance where provider wording is unstable
- final publishable pricing remains governed by explicit validation gates

This is preferable to both extremes:

- pure keyword matching, which is brittle and opaque when providers drift
- pure AI selection, which is hard to reproduce and cannot prove billing
  correctness

## Planned Implementation Phases

The detailed implementation plan is:

`2-twin2clouds/implementation_plans/2026-06-13_ai_assisted_pricing_candidate_review.md`

The phases are:

- Candidate Contract and Deterministic Match Report
- AI Semantic Review Adapter
- Agreement and Disagreement Resolver
- Review Decision Persistence in the Management API
- Read-only Review API and Flutter UI Workflow
- Thesis and Operations Guardrails

## Open Research Notes

- The first implementation should likely send only the top 5-10 candidates
  after hard filters to AI.
- AI confidence should be shown carefully, if at all; it must not look like a
  correctness guarantee.
- Reviewed decisions may need both DB persistence for user context and export
  formats for reproducible thesis examples.
