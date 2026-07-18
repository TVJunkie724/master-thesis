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

## Calculation And Evidence

Calculate creates a durable server-owned optimizer run for the current twin.
For a new twin, the workspace creates the draft identity first and reuses it
when a calculation is retried. Saving a draft does not save or alter a
calculation result.

Each new successful run also freezes the exact provider services, SKUs, plans,
capacities, storage classes, runtime settings, formula assumptions, and pricing
evidence needed to reproduce deployment. These values are read-only. A historical
run created before this contract can still be inspected, but the user must calculate
again before it can be selected for deployment.

The default result remains concise. Expand **Calculation trace** only when
provenance is needed. Current results provide nested, read-only details for the
pricing intent, immutable provider catalogs, exact six-edge transfer routes,
provider billing pools, native tier contributions, and solver diagnostics.
Historical results remain readable and state explicitly when exact route
evidence was not yet recorded.

## Workload Versus Provider Pricing

The workspace records workload quantities and intent. It does not ask the user to
manually normalize AWS/Azure/GCP catalog units. The Optimizer's provider contracts and
formulas perform provider-specific billing calculations and return comparable monthly
cost results with trace metadata.

The Twin capabilities task keeps two provider-specific Azure Digital Twins assumptions
under a collapsed advanced section:

- average Query Units consumed by one logical query;
- average response payload size in KB.

Both default to `1.0`. Change them only when measurements or an explicit scenario
assumption justify a different value. Azure bills response operations in one-KB
increments, so a response slightly larger than one KB consumes two operation units.
The calculation evidence view records the supplied values, their source, the derived
operation/query-unit quantities, and the three separate Azure Digital Twins cost
components.

## Artifacts

Data contracts, user functions, IoT payloads, hierarchy/state-machine files, and scene
assets are validated through typed upload/editor boundaries. Read-only generated views
help inspection; generated deployment files are not independent user-owned truth.
