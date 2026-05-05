# Deployer Templates

This directory contains versioned, read-only project templates used as source
material for deployment workspaces.

The canonical default template is `digital-twin/`. Runtime deployments must be
materialized under `upload/<project-name>/` and must not mutate files in this
template directory.

During the transition, `upload/template/` may still exist as a local legacy
working copy with real credentials for supervised tests. It is intentionally not
deleted by repository cleanup.
