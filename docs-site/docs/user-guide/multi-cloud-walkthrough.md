# Multi-Cloud Walkthrough

This walkthrough exercises the intended workflow without prescribing one provider as
the correct result. The selected architecture depends on workload, region, pricing
evidence, provider capability, and the active cost profile.

## 1. Start Safely

For a no-cloud walkthrough:

```bash
./thesis.sh demo --scenario showcase
```

For real local persistence and services without cloud mutations:

```bash
./thesis.sh up --no-flutter
./thesis.sh flutter
```

## 2. Confirm Account-Level Pricing Readiness

From the dashboard, open **Pricing Review**. Review AWS, Azure, and GCP independently:

1. confirm the displayed pricing account/project context;
2. inspect cache age and latest run;
3. refresh only when the intended pricing CloudConnection is available;
4. expand evidence when a provider is review-required;
5. record a mapping decision only after comparing selected and rejected candidates.

Do not create a throwaway twin merely to refresh global pricing.

## 3. Create The Twin And Workload

Create a twin and complete **Define twin** and **Describe workload**. Representative
inputs include device count/message frequency and size, processing executions/duration,
retention/storage quantities, and required Digital Twin/visualization capabilities.

The inputs describe workload intent. They do not encode provider SKU names or prices.

## 4. Calculate And Inspect Alternatives

In **Choose architecture**:

1. confirm pricing readiness;
2. calculate alternatives;
3. compare per-layer provider assignments and monthly cost breakdowns;
4. expand calculation trace/evidence when a result is surprising;
5. select the architecture accepted for deployment.

```text
workload
  -> AWS/Azure/GCP component costs
  -> valid five-layer provider paths
  -> minimum-cost scoring
  -> selected path with component/layer trace
```

A mixed path may require inter-cloud connector functions and transfer pricing. A cheap
individual service does not automatically produce the cheapest complete path.

## 5. Prepare Deployment

The selected path determines required provider deployment connections and artifacts.
Complete cloud access, data contracts, user logic, and twin assets. Unsupported provider
capabilities or missing cross-cloud glue must appear as readiness findings rather than
being silently ignored.

## 6. Validate Without Deploying

Run configuration validation and provider preflight. Review manifest/artifact findings,
required provider permissions and versions, stale preflight results, packages, and asset
constraints. Stopping here is the safe integrated development workflow; it proves local
contracts, not live provider deployment.

## 7. Optional Supervised Deployment

Only continue with approved accounts, cost expectations, regions, cleanup, and
credentials. Follow persisted operation/SSE logs, inspect outputs and verification,
then destroy and confirm cleanup evidence.

Live operation evidence belongs to the opt-in E2E/thesis evidence issue, not routine
documentation verification.
