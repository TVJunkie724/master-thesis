# User Guide

The supported research workflow is:

```text
load the configured local owner profile
  -> create/import/duplicate a Twin draft
  -> configure typed scenario and bounded functions
  -> calculate and review cost-only Six-layer evidence
  -> select existing deployment CloudConnections
  -> run readiness and repair
  -> confirm immutable deployment
  -> verify telemetry and open L4/L5 access links
  -> confirm Destroy and inspect cleanup evidence
```

There is no interactive sign-in route in the thesis PoC. Application startup
loads the configured local owner profile; provider CloudConnections remain
separate deployment authority.

Start with [Dashboard and Twins](dashboard-and-twins.md), then continue through
[Configuration Workspace](configuration-workspace.md),
[Cloud Accounts](cloud-accounts.md),
[Deployment and Verification](deployment.md), and the
[Multi-Cloud Walkthrough](multi-cloud-walkthrough.md).

The offline demo presents deterministic examples of this workflow without
cloud credentials or cost. It is useful for UI review but does not prove live
provider functionality.
