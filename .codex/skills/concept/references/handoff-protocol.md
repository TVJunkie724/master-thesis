# Handoff Protocol

When work needs to move to another agent, produce a **Handoff Document** — a self-contained file that gives a fresh agent in a completely new chat everything needed to start without asking follow-up questions.

## Handoff Document Location

Store alongside the concept / phase it belongs to:

```
twin2multicloud_flutter/docs/[pillar]/
├── ROADMAP_[PILLAR].md
├── concepts/
├── phases/
└── handoffs/
    └── HANDOFF_[PHASE]_[TARGET_AGENT].md
```

(Create the `[pillar]/` folder under `twin2multicloud_flutter/docs/` the first time a pillar needs documentation. See `pillar-organization.md` for the full layout.)

## Handoff Document Structure

Every handoff document MUST include all 8 sections:

```markdown
# Handoff: [Phase / Concept Name] → [Target Agent]

## 1. Context
- Which pillar this belongs to
- Link to the roadmap and the specific phase / concept
- What has been decided and approved by the concept agent

## 2. Objective
Exactly what the target agent must accomplish. One clear goal.

## 3. Required Reading
List of ALL documentation files the target agent must read.
Full repo-relative file paths — no ambiguity. Always include:
- `FRONTEND_ARCHITECTURE.md`
- `integration_vision.md`
- `references/flutter-guardrails.md`
- The concept and phase documents themselves

## 4. Scope
- What is IN scope for this handoff
- What is explicitly OUT of scope
- What has been deferred (link to the deferral or future phase)

## 5. Constraints & Decisions
Decisions already made by the concept agent that the target agent MUST respect.
These are not suggestions — they are binding. Examples:
- "Use existing `BrandedAppBar` widget — do not create a new app bar"
- "Wizard Step 3 must save draft via Management API `PUT /twins/{id}/wizard-step3` — do not call Deployer directly"
- "BLoC ownership: a single `WizardBloc` covers all 3 steps; do not split into per-step BLoCs"

## 6. Acceptance Criteria
How the user will know the work is done. Concrete, verifiable criteria.
For UI work, always include:
- `flutter analyze` clean
- `flutter test` green
- `flutter build web` AND `flutter build linux` succeed
- All async branches handle loading / error / empty

## 7. Dependencies
- What must exist before this work can start (e.g. "Management API endpoint X must be implemented")
- What other phases / concepts this depends on
- Current status of those dependencies (link to FR / BUG tracker if blocking)

## 8. Open Questions (if any)
Questions the concept agent could not resolve that the target agent
may need to discuss with the user.
```

## Handoff Rules

| Rule | Why |
|------|-----|
| Must be **self-contained** | The receiving agent has zero context from this chat |
| Include **full repo-relative file paths** for all referenced documents | No ambiguity — the agent reads exactly what you point to |
| State **binding decisions** explicitly | The architect / builder must not re-decide what was already settled |
| The concept agent does NOT review implementation | That is the auditor's job — produce a separate handoff for the auditor too |
| One handoff per deliverable unit | Keep handoffs focused — one phase, one objective |
| Reference the session ID from `.ai-session.json` if relevant | Helps the receiving agent locate WIP commits |

## Handoff Targets

| When... | Produce handoff for... |
|---------|------------------------|
| Concept / phase approved, ready for implementation planning | **architect** |
| Implementation plan exists, ready to build | **builder** |
| Implementation complete, needs audit | **auditor** |

## Important

This chat stays clean. No other agent personas (Architect, Builder, Auditor) are EVER invoked inside the concept agent's chat. The concept agent operates in its own conversation, always.
