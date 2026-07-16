# Configuration Workspace

The workspace replaces one long three-page form with five phases and smaller tasks.
The sidebar provides orientation, completion/attention status, and direct access to
navigable tasks; blocked tasks explain their prerequisite.

## Phases And Tasks

| Phase | Tasks |
|---|---|
| Define twin | identity and mode |
| Describe workload | scenario/currency, device traffic, processing, retention, twin capabilities |
| Choose architecture | pricing readiness, calculate alternatives, compare/select |
| Prepare deployment | cloud access, data contracts, user logic, twin assets |
| Review configuration | summary, readiness findings, validation/preflight |

The conceptual phases replace the old UX, but typed backend contracts retain legacy
step projections internally where needed for compatibility.

## Dependency Rules

```text
twin identity
   -> complete workload
      -> pricing ready enough to calculate
         -> calculation result / selected architecture
            -> required provider cloud access
               -> deployment artifacts
                  -> validation and preflight
```

Users may revisit completed tasks. A material configuration edit can invalidate a
calculation, readiness result, or `configured` state. The workspace shows the next
recommended task rather than pretending downstream results remain current.

## Workload Versus Provider Pricing

The workspace records workload quantities and intent. It does not ask the user to
manually normalize AWS/Azure/GCP catalog units. The Optimizer's provider contracts and
formulas perform provider-specific billing calculations and return comparable monthly
cost results with trace metadata.

## Artifacts

Data contracts, user functions, IoT payloads, hierarchy/state-machine files, and scene
assets are validated through typed upload/editor boundaries. Read-only generated views
help inspection; generated deployment files are not independent user-owned truth.
