# Configuration Workspace Phase 6: Review And Validation

## Objective

Provide a compact final review, actionable readiness findings, and the
authoritative distributed validation/finish path.

## Backend Authority

The Management API's transition to `configured` invokes
`ConfigurationValidationService`, which validates local prerequisites and calls
Optimizer and Deployer validation boundaries. This is the configuration
preflight. The Flutter client must not claim or emulate a stronger check.

## Screens

- Configuration summary: identity, workload, architecture path, required cloud
  access, and deployment section readiness.
- Readiness findings: missing/invalid access or artifacts, invalidation state,
  and direct navigation to the owning task.
- Validation and preflight: authoritative boundary summary and Finish command
  state. The stable footer owns the command.

## Error Handling

- Client readiness gates obvious invalid requests but never replaces server
  validation.
- Structured Management API validation failures remain visible through the
  existing BLoC error boundary and preserve the draft.
- Failed Finish never navigates or marks local state configured.
- Successful Finish navigates to Twin Overview; deployment remains explicit.

## Verification

- Findings map every missing required artifact to exactly one task.
- Missing deployment access maps to Cloud Access.
- Invalidation maps back to architecture review.
- Finish is unavailable until client readiness passes and server errors remain
  visible.
- Full Flutter tests and analyzer pass.

