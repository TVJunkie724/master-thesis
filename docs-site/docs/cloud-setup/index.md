# Cloud Setup

Cloud setup is intentionally small. The operator provides an existing isolated
AWS account, Azure subscription, or GCP project with billing already usable and
a pre-existing non-root administrator credential.

1. Add/import the credential as a named deployment CloudConnection.
2. Review the detected identity and target scope.
3. Bind it only to a Twin whose resolved graph uses that provider.
4. Run identity validation and graph-derived readiness.
5. Review and explicitly confirm any supported bounded preparation.
6. Complete external prerequisites manually and rerun readiness.

The PoC does not create cloud accounts/subscriptions/projects, repair billing,
approve quotas, override organization policy, grant tenant-wide consent,
accept legal terms, or manage credential lifecycle.

See [AWS](aws.md), [Azure](azure.md), [Google Cloud](gcp.md), and the official
[Provider Links](provider-links.md). Provider commands are not run as part of
ordinary documentation verification.
