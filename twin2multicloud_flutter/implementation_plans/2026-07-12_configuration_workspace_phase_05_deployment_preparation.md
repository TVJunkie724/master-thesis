# Configuration Workspace Phase 5: Deployment Preparation

## Objective

Present deployment artifacts as requirement-driven tasks without rewriting or
duplicating the validated JSON, code, ZIP, GLB, and provider-specific editor
implementations.

## Task Ownership

- Data contracts: core configuration, event/device contracts, payload schemas,
  and read-only generated provider/optimizer projections.
- User logic: processors, event actions, feedback functions, requirements, and
  state machines enabled by validated contracts.
- Twin assets: provider hierarchy, scene config/GLB when required, and dashboard
  user config when required.
- Cloud access remains the dedicated Phase-2 task.

## Architecture

- `Step3Deployer` accepts a typed task focus and composes existing editor blocks.
- Shared editor/validation code is reused; focused layouts only control
  composition and visibility.
- `DeployerConfigRequirements` and `DeployerConfigReadiness` remain the sole
  conditional requirement and completion projections.
- Not-required tasks render a concise domain state and no inert editors.
- ZIP upload is a secondary accelerator in Data Contracts, never the primary
  information architecture.

## Verification

- Every deployer artifact ID appears in exactly one focused task.
- Required/optional matrices cover AWS, Azure, GCP, 3D, feedback, event actions,
  state machines, and dashboard config.
- Dynamic editors still unlock only after their contract dependencies validate.
- All existing server validation, GLB upload/delete, ZIP import, and save tests
  pass.
- Full analyzer and Flutter tests pass.

