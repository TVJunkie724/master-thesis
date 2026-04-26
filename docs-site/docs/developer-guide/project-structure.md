# Project Structure

The repository contains the integrated thesis platform and the original service projects it builds on.

![Project structure diagram](../references/diagrams/project_structure_diagram_1763756022092.png)

## Main Directories

| Directory | Purpose |
|-----------|---------|
| `twin2multicloud_backend/` | Management API, persistence, orchestration, and the UI-facing backend contract. |
| `twin2multicloud_flutter/` | Flutter application for scenario configuration, optimization review, deployment control, and twin operation. |
| `2-twin2clouds/` | Optimizer service derived from the original Twin2Clouds cost-modeling project. |
| `3-cloud-deployer/` | Deployer service derived from the cloud deployment bachelor project. |
| `twin2multicloud-latex/` | Thesis source. |
| `docs-site/` | Canonical documentation site. |

Service-local docs under `2-twin2clouds/docs/` and `3-cloud-deployer/docs/` are migration source material. They can remain while content is being rewritten, but new thesis/developer documentation should live in `docs-site/`.

## Important Integration Detail

The original projects were developed as separate systems. In this thesis repository, the Management API is the integration boundary:

```text
Flutter UI
  -> Management API
    -> Optimizer
    -> Deployer
```

That means old service-local setup docs remain useful as source material, but the integrated developer workflow should be described from the repository root.

Generated deployment files, uploaded project bundles, Terraform state, and local credential files are runtime material. They should not be treated as architectural source files just because they appear in the repository during the transition.
