# Documentation Standards

All documents created by the `concept` skill MUST comply with these standards. The project does not (yet) ship a separate AI-DOC-GOVERNANCE skill — these are the standards.

## YAML Frontmatter (Mandatory)

```yaml
---
title: "[Document title]"
description: "[1-sentence description]"
tags: [tag1, tag2, tag3]
lastUpdated: "YYYY-MM-DD"
version: "1.0"
---
```

## Provenance Tracking (Mandatory)

Place a comment block immediately after the frontmatter:

```markdown
<!-- SOURCES:
- [List all source documents, files, conversations, decisions that informed this document]
- e.g. FRONTEND_ARCHITECTURE.md §4 "User Workflow"
- e.g. integration_vision.md §3.A "Orchestrator role"
EXTRACTED: YYYY-MM-DD | VERSION: 1.0
-->
```

If you cannot list a real source, the document isn't ready to commit.

## Language Rules

| Aspect | Standard |
|--------|----------|
| Document language | English (the rest of the repo is mixed English / German — pick English for new frontend docs to stay consistent with `FRONTEND_ARCHITECTURE.md`) |
| Technical terms | English (Flutter, BLoC, SSE, dio, …) |
| Code references | English (class names, file paths) |
| Deviations | If the user prefers German for a specific document, follow the user's preference and note it in the frontmatter |

## Content Rules

| Rule | Description |
|------|-------------|
| **No placeholders** | Every example is real, every reference resolves to an existing path or known future path |
| **No TODOs** | Either complete the section or do not commit it |
| **Tables for facts** | Fields, properties, scope → tables |
| **Prose for rules** | Decisions, rationale, guardrails → natural language |
| **Cross-references** | Link related documents, never duplicate content |
| **Scope tables** | For domain documents, include an explicit `In scope ✅ / Out of scope ❌` table |
| **Relative paths** | Use repo-relative paths like `twin2multicloud_flutter/lib/screens/wizard/` — never absolute Windows / macOS paths |

## Quality Checklist

Before committing any document:

- [ ] YAML frontmatter complete?
- [ ] Provenance comment present and real?
- [ ] Scope table with ✅ / ❌ (if domain document)?
- [ ] No placeholders or TODOs?
- [ ] Cross-references resolve?
- [ ] Language consistent with neighbouring docs?
- [ ] All paths relative?
- [ ] No Mermaid diagrams (ASCII only)?
- [ ] Anchored in a Roadmap (`ROADMAP_<PILLAR>.md`)?
