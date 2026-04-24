---
name: concept-review
description: >
  Use this project-specific Twin2MultiCloud skill when the user asks to "review concept", "concept review", "review the concept document", "check the concept", "concept quality check", or "validate the concept". Use for reviewing concept documents against 4 mandatory criteria (+ 1 UI-specific criterion).
metadata:
  project: master-thesis
  source: .claude/concept-review
---


# Concept Review — Mandatory Quality Criteria

Read and apply all guardrails from `references/flutter-guardrails.md` before any work.

## Instructions

Review the concept against these **4 mandatory criteria** (+ 1 additional for UI / Flutter concepts):

### Criterion 1: Executability

Can a downstream agent (`architect`, `builder`) implement every point without follow-up questions? Are there vague phrases like "if needed", "where applicable", "evaluate whether…" without a concrete expected outcome?

### Criterion 2: Completeness

Are any steps missing that the agent will need? For example:
- How does the agent merge the phase? (branch, target, strategy)
- Which exact `flutter` / `docker compose` commands?
- What happens when a debug step fails?
- Which Management API endpoints does the concept assume? Do they exist?

### Criterion 3: Over-Engineering

Are any tasks present that don't belong in this phase? Compare against the explicit Non-Goals — do tasks contradict the scope-out list?

### Criterion 4: Contradictions

Do the numbers (test counts, baselines, percentages) match reality? Does the document reference files / branches / endpoints that actually exist? Cross-check against `FRONTEND_ARCHITECTURE.md`, `integration_vision.md`, and the live Management API contract.

### Criterion 5 (UI / Flutter concepts only): Clean Architecture & Future-Proofing

- **Layer separation** — does the concept respect the BLoC / services / presentation split? Are there hidden assumptions that a widget will perform HTTP calls or hold business logic?
- **Reuse-first** — does the concept reference existing widgets in `lib/widgets/` before proposing new ones?
- **Tokens** — does it call out the design tokens it relies on (or list the tokens it requires to be added)?
- **Management API only** — does every backend interaction go through the Management API? Any hint of a direct call to Optimizer (5003) / Deployer (5004) is a finding.
- **ASCII layouts** — for every UI element described, is there at least one ASCII layout / widget tree sketch (or an explicit handoff note that the architect will produce them)?
- **Desktop + Web** — does the concept consider both targets, or is it implicitly mobile / single-platform?

## Output Format

For **each finding**:

| Field | Content |
|-------|---------|
| **Line number** | Exact line(s) in the document |
| **Problem** | What is wrong or missing |
| **Priority** | 🔴 High / 🟡 Medium / 🟢 Low |
| **Suggested fix** | Concrete, applicable correction text |

## Process

1. Read the concept document fully.
2. Read all referenced documents (concepts, roadmaps, phases, `FRONTEND_ARCHITECTURE.md`, `integration_vision.md`).
3. Verify referenced API endpoints exist (`docker ps`, hit `/openapi.json` on the Management API when available).
4. Check against all 4 (or 5) criteria.
5. Produce the finding list.
6. Present findings to the user for decision.
7. Apply approved fixes carefully — nothing already approved may regress.
8. Repeat the review until 0 findings remain.
