# Cloud Setup

The supervised PoC uses one preconfigured administrator credential for each
provider involved in pricing or deployment. Twin2MultiCloud does not create
cloud identities, generate minimal credentials, or manage permission packs and
rotation.

## Safe sequence

1. Create or select an isolated thesis account, subscription, or project.
2. Enable billing and the provider services required by the selected
   Six-layer deployment.
3. Create a non-root administrator credential outside the application.
4. In **Settings -> Cloud Accounts & Access**, register the credential through
   the write-only form and verify the displayed provider scope.
5. Validate it, assign pricing/deployment purpose as required, and bind the
   deployment connection to the Twin.
6. Run deployment preflight. Resolve only the concrete provider prerequisite
   reported by the check.
7. Run live deployment, verification, destroy, and credential revocation only
   as an explicitly supervised E2E session.

The application stores the CloudConnection encrypted and returns only
non-secret metadata. Never use a root/break-glass credential, commit provider
keys, or paste credentials into logs and issue bodies.

- [AWS](aws.md)
- [Azure](azure.md)
- [Google Cloud](gcp.md)
- [Provider Links](provider-links.md)
