# Configuration Workspace Phase 2: Identity And Cloud Access

## Objective

Separate twin identity from deployment authorization. A user can describe and
optimize a twin without binding deployment credentials. After architecture
selection, Cloud Access requests only the deployment connections required by
the selected provider path.

## Changes

- Make `Define twin` a focused name and execution-mode form.
- Add a dedicated Cloud Access task content widget.
- Filter the wizard connection inventory to `purpose=deployment`; pricing
  connections must never be selectable for deployment.
- Restrict rendered provider sections to providers used by the selected
  architecture.
- Change progression and edit restoration so credentials do not gate workload
  description.
- Keep final readiness and Finish blocked until every selected-path provider has
  valid/bound deployment access.

## Contract Rules

- `selectedCloudConnectionIds` remains the persistence contract.
- Legacy encrypted credentials remain read-only migration compatibility; new
  selections use CloudConnection IDs.
- Provider requirements come only from the selected `calcResult.cheapestPath`.
- Pricing CloudConnections are excluded in the BLoC before presentation.
- Removing or invalidating a required connection immediately marks Cloud Access
  as attention and keeps Finish unavailable.

## Files

- Modify `step1_configuration.dart`, `wizard_state.dart`,
  `wizard_init_service.dart`, `wizard_bloc.dart`, and
  `cloud_connections_group.dart`.
- Add `features/configuration_workspace/presentation/cloud_access_task.dart`.
- Route task-specific content from `wizard_screen.dart`.
- Extend BLoC, journey, widget, and initialization tests.

## UX States

- No architecture: task remains blocked and cannot render the form.
- Required provider missing: show its connection selector and a concise
  requirement explanation.
- Required provider bound but unvalidated: attention with validation action.
- All required providers valid: complete summary.
- Provider not selected by architecture: do not request access; summarize it as
  not required in review later.
- API errors stay provider-local and retryable.

## Verification

- A named twin reaches workload configuration with no credentials.
- An AWS/Azure path renders exactly AWS and Azure deployment connections.
- Pricing-purpose connections are absent.
- A missing required provider blocks final completion, not optimization.
- Existing legacy drafts hydrate without losing bindings.
- Full Flutter tests and analyzer pass.

## Non-Goals

- Creating admin/bootstrap credentials in this screen.
- Managing account-scoped pricing credentials.
- Changing CloudConnection persistence or secret handling.

