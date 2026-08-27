# Active planning lifecycle

Twin2MultiCloud keeps a small active documentation set instead of permanent
per-feature roadmap, phase and handoff trees.

## Durable documents

- the thesis PoC target concept;
- the research questions and evaluation design;
- the current execution plan while empirical work is unfinished;
- the credential/security concept;
- current architecture, user and developer documentation; and
- the development and decision log.

Add a focused future-work concept only when it explains a scientifically
relevant extension boundary. Do not label it as committed or planned runtime
functionality.

## Temporary documents

A material implementation may use one bounded concept and one implementation
plan. They must state scope, exclusions, dependencies, acceptance evidence and
the affected research/safety responsibility. Avoid nested pillar roadmaps,
phase trackers, handoff files and duplicate TODO lists.

After implementation and verification:

1. migrate durable rationale to `docs/development_and_decision_log.md`;
2. update current architecture/user/developer documentation;
3. update the active execution status;
4. remove the temporary concept/plan if it no longer guides unfinished work;
5. rely on Git history for the detailed implementation sequence.

Current truth must never depend on a completed handoff or historical phase
file.
