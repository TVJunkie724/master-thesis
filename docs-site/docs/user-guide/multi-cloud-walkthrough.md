# PoC Walkthrough

Use the offline demo to inspect the result of the PoC without accounts or
cloud cost. Use the integrated stack when you need real local persistence.

## 1. Open the demo

After installing the [prerequisites](../getting-started/fresh-clone.md), run
from the repository root:

```bash
./thesis.sh demo --setup
```

**Expected:** a populated dashboard, a fixture user and a visible demo banner.
No login, Docker or cloud credentials are required.

## 2. Inspect the main workflow

| Action | What to look for |
|---|---|
| Open a Twin | configuration and lifecycle state |
| Inspect the Configuration Workspace | five phases from workload to review |
| Open a populated calculation result | provider assignments and estimated monthly costs |
| Expand calculation evidence | assumptions and the resource selections behind the result |
| Open Pricing Review | provider readiness and review-required states |
| Inspect deployment history | operation status and log presentation |

All values and operations here are fixtures. They illustrate the workflow,
not live pricing or deployed infrastructure. Restarting discards demo edits.

For empty and failure states, restart with:

```bash
./thesis.sh demo --scenario empty
./thesis.sh demo --scenario degraded
```

## 3. Use local persistence

```bash
./thesis.sh up --setup
```

Select **Continue in local development**, then create a Twin and save its
identity/workload. **Expected:** the Twin persists in the Management database
and can be reopened. Cloud credentials are not required for startup.

Calculation uses reviewed pricing catalogs; inspect their readiness and
recorded source before interpreting a cost result. A pricing refresh may
contact a provider. Follow [Configuration Workspace](configuration-workspace.md)
and [Pricing Review](pricing-review.md) when exploring those steps.

## Cloud deployment is a separate step

The current profile resolver defaults to off; new deployment packages need a
resolved architecture and Manifest v3. The graph compiler is implemented, but
the L4→L5 binding gap and final live verification remain open.
See [Results and Limits](../runtime/known-limitations.md) before using
[Cloud Setup](../cloud-setup/index.md) or [Deployment](deployment.md).

For local failures, use [Troubleshooting](../runtime/troubleshooting.md).
