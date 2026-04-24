# Pillar-Based Frontend Documentation Structure

## Directory Layout

Each major area (pillar) of `twin2multicloud_flutter` gets its own subfolder under `twin2multicloud_flutter/docs/`. Every pillar subfolder contains `concepts/` and `phases/`:

```
twin2multicloud_flutter/docs/
├── README.md                          # Index of pillars (create when ≥ 1 pillar exists)
├── feature-requests/                  # Central FR tracker (cross-pillar)
├── bugs/                              # Central bug tracker (cross-pillar)
│
├── [pillar-a]/                        # One subfolder per pillar (e.g. wizard, dashboard)
│   ├── ROADMAP_[PILLAR_A].md          # Roadmap = anchor point
│   ├── concepts/
│   │   ├── CONCEPT_[NAME].md
│   │   └── ...
│   ├── phases/
│   │   ├── PHASE_[NUMBER]_[NAME].md
│   │   └── ...
│   └── handoffs/
│       └── HANDOFF_[PHASE]_[TARGET].md
│
├── [pillar-b]/
│   ├── ROADMAP_[PILLAR_B].md
│   ├── concepts/
│   ├── phases/
│   └── handoffs/
│
└── ...
```

There are **no** top-level `concepts/` or `phases/` folders. Every concept and phase belongs to exactly one pillar. Cross-cutting concerns (routing, theme, error handling, accessibility) live in a `cross_cutting` pillar.

Existing top-level docs (`twin2multicloud_flutter/docs/TODO_infrastructure_deployment.md`, etc.) can stay where they are — folder them under a pillar only when their content stabilizes into a concept.

## The Roadmap is the Anchor

Every pillar MUST have a roadmap file. The roadmap is the **single anchor point** that:

- Lists all concepts with links to their concept documents
- Lists all phases with links to their phase documents
- Defines the order of execution
- Tracks status (⬜ Planned, 🔄 In Progress, ✅ Complete)
- Notes Management API dependencies for each phase (link to FR if missing)

## Phase Numbering — NO Renumbering

**Phases are NEVER renumbered.** Once a phase has a number, it keeps that number forever.

When inserting a new phase between two existing phases:

| Situation | Solution | Example |
|-----------|----------|---------|
| New phase between 1.2 and 1.3 | Use extended numbering | `1.21` or `1.2a` |
| New phase between 3 and 4 | Use extended numbering | `3.1` |
| New sub-phase of 2.1 | Use deeper numbering | `2.1.1`, `2.1.2` |

**Why?** Renumbering breaks every reference to a phase across all documents, conversations, and agent contexts. Extended numbering preserves all existing references — including handoffs already in flight.

## Pillars vs. Code Folders

Pillars in documentation do NOT have to mirror folders in `lib/` 1:1. A pillar is a *planning unit*, a folder in `lib/` is a *code unit*. Example: the pillar `wizard` may produce code across `lib/screens/wizard/`, `lib/bloc/wizard/`, and `lib/widgets/wizard/`. The roadmap of a pillar should call out which code folders it touches.
