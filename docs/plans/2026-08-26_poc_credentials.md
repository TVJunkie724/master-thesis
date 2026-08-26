# PoC credential boundary

Status: active thesis scope decision (2026-08-26)

## Decision

The proof of concept does not create cloud identities or derive least-privilege
permission sets. For each provider, the operator supplies one preconfigured,
privileged administrator credential from an isolated thesis account,
subscription, or project. The same credential may be registered for pricing
and deployment where the provider flow requires both purposes.

`root` or tenant-wide break-glass credentials are outside the accepted PoC
boundary. The operator remains responsible for preparing and later revoking
the supplied credential.

## Retained implementation

- Management stores submitted CloudConnections encrypted and exposes only
  non-secret metadata.
- Secret values are write-only at API and Flutter boundaries, redacted from
  logs and errors, and forwarded only for the current downstream request.
- Optimizer and Deployer validate the supplied credential against the actual
  provider operations required by the selected Six-layer deployment.
- Deployment readiness reports missing, invalid, or stale validation; it does
  not infer permissions from a declared permission-pack version.
- Tests continue to scan transport, persistence, diagnostics, and responses
  for credential leakage.
- Credentials created for resources inside a deployed Twin, such as a bounded
  Grafana viewer identity, remain runtime outputs when the selected provider
  service requires them. They are not deployment-authority bootstrap identities.

## Explicitly excluded

- guided cloud bootstrap sessions and provider bootstrap adapters;
- automatic IAM user, role, service-principal, or service-account creation;
- generated minimal credentials, permission packs, and permission-set versioning;
- automatic rotation, revocation, organization onboarding, and production
  credential lifecycle management;
- any claim that the PoC credential is least privilege or production ready.

## Evaluation statement

The thesis validates whether preconfigured credentials can drive the complete
Six-layer workflow safely enough for a supervised PoC. It does not evaluate an
identity-provisioning product. The broader least-privilege lifecycle is future
work and a stated limitation of the evaluation.
