# Source Provenance Appendix

The current documentation was reconstructed from the integrated codebase rather than
copied from one predecessor site. This appendix records the source families used so the
platform evolution remains auditable without duplicating every current explanation in
a migration table.

## Source Families

| Source family | Original contribution | Current treatment |
|---|---|---|
| `2-twin2clouds/docs/` | standalone Optimizer architecture, provider pricing, formulas, patterns, credentials, tests, and legacy UI | validated against the pricing registry, evidence pipeline, calculation engine, profiles, and tests; current behavior is documented under Optimizer and Pricing Review |
| `3-cloud-deployer/docs/` | standalone Deployer architecture, provider setup, deployment, user functions, simulator, patterns, and CLI/API usage | validated against manifests, storage/workspaces, provider/Terraform implementations, bootstrap artifacts, and tests; legacy CLI/layer paths are historical |
| root plans, assessment, integration and frontend documents | architecture debt, intended integration, decisions, roadmaps, and refactoring evidence | used to explain motivation and evolution; never treated as stronger evidence than current code/contracts/tests |
| original papers, PDFs, and diagrams | five-layer model, project lineage, and research context | preserved centrally and linked in context from architecture and references |

## Evaluation Rule

For each material concern, evidence was resolved in this order:

1. current code, schemas, configuration, migrations, and executable contracts;
2. current deterministic tests and safe local runtime behavior;
3. merged implementation plans and GitHub issue history for decision rationale;
4. legacy HTML/Markdown and papers for historical context.

When an older source conflicts with the executable system, the current documentation
states the present behavior and records the transformation in
[Original to Current State](../architecture/evolution.md) or the relevant component.

## Historical Material

Historical files are not part of the user workflow and are not linked as current setup
instructions. They remain in the repository for now because some contain unique
research context, provider investigations, or implementation history. Their later
removal needs a dedicated archive/cleanup check, especially around ignored credential
material.

Active future work is tracked in GitHub Issues and the
[Refactoring Roadmap](../architecture/refactoring-roadmap.md), not in legacy
`future-work` or TODO documents.
