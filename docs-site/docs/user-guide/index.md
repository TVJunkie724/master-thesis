# User Guide

Twin2MultiCloud separates account-level cloud readiness from twin-specific design and
deployment. The main user journey is:

```text
sign in
  -> maintain cloud accounts
  -> review provider pricing readiness
  -> create/configure a twin
  -> calculate and select architecture
  -> validate deployment readiness
  -> deploy, inspect logs/outputs, verify, destroy
```

The offline demo exposes the same screens with deterministic data. Production login
remains externally gated; local development uses an explicit development sign-in.

- [Dashboard and Twins](dashboard-and-twins.md)
- [Cloud Accounts](cloud-accounts.md)
- [Configuration Workspace](configuration-workspace.md)
- [Pricing Review](pricing-review.md)
- [Deployment and Verification](deployment.md)
- [Multi-Cloud Walkthrough](multi-cloud-walkthrough.md)
- [Offline Demo](demo.md)
