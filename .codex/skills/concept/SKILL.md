---
name: concept
description: >
  Use this project-specific Twin2MultiCloud skill for Flutter strategy, scope,
  concept documents, phase planning, or roadmap requests that do not require
  code or a detailed implementation plan.
metadata:
  project: master-thesis
  source: thesis-poc-documentation-lifecycle
---

# Concept — Thesis-PoC frontend planning

Read `references/flutter-guardrails.md` before any work. For a material
document change, also read `references/documentation-standards.md` and
`references/pillar-organization.md`.

## Mission

Shape a coherent Flutter workflow that is sufficient to answer the thesis
research questions. Prefer the smallest clear concept that preserves
traceability, cloud-mutation safety and reproducibility. Do not plan a generic
cloud-management product.

## Boundaries

- Do not write Dart code or detailed widget/BLoC implementation plans.
- Do not run builds, tests or provider operations.
- Flutter calls only the Management API.
- Do not expose inactive objectives, architecture choices or product
  administration merely to demonstrate extensibility.
- Map every retained UI responsibility to a research question, safety need or
  reproducibility need.

## Required context

Read only the relevant parts of:

1. `docs/plans/2026-08-26_thesis_poc_target_concept.md`;
2. `docs/research/research_questions_and_evaluation_design.md`;
3. `docs/plans/2026-08-26_thesis_poc_execution_plan.md`;
4. `FRONTEND_ARCHITECTURE.md`;
5. `integration_vision.md`;
6. `twin2multicloud_flutter/README.md`; and
7. the affected current code and Management OpenAPI contract.

Do not load every historical document in `twin2multicloud_flutter/docs/`.

## Workflow

1. State the research/safety responsibility and the user outcome.
2. Define in-scope and out-of-scope behavior.
3. Check the current UI and Management contract before proposing new surface.
4. Prefer consolidation and reuse over new routes, pillars or frameworks.
5. Record decisions and dependencies in one current concept document.
6. Hand the approved concept to `architect` in the current task context; do not
   create a permanent handoff document.

Concepts may include an execution sequence, but must not become open-ended
product roadmaps. Temporary phase or implementation documents are removed
after their implemented decisions are reflected in current architecture,
developer and decision documentation. Git preserves the detailed history.

## Gaps

When the UI needs a missing backend contract, report the exact gap and target
service. Use a GitHub Issue only when the user requests issue tracking; do not
create parallel local feature-request or bug backlogs.

## Related skills

- `architect` creates the bounded implementation plan.
- `mocker` may create a temporary visual prototype when it materially reduces
  UI uncertainty.
- `builder` implements an approved plan.
- `auditor` verifies the result against that plan.
