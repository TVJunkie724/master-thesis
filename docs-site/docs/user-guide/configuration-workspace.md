# Configuration Workspace

The workspace replaces one long three-page form with five phases and smaller tasks.
The sidebar provides orientation, completion/attention status, and direct access to
navigable tasks; blocked tasks explain their prerequisite.

## Phases And Tasks

| Phase | Tasks |
|---|---|
| Define twin | identity and mode |
| Describe workload | scenario/currency, device traffic, processing, retention, twin capabilities |
| Choose architecture | pricing readiness, calculate alternatives, review recommendation |
| Prepare deployment | cloud access, data contracts, user logic, twin assets |
| Review configuration | summary, readiness findings, validation/preflight |

The conceptual phases replace the old UX, but typed backend contracts retain legacy
step projections internally where needed for compatibility.

## Dependency Rules

```text
twin identity
   -> complete workload
      -> pricing ready enough to calculate
         -> calculation result / verified deployment selection
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

After calculation, the workspace asks the Management API to verify and select the
whole optimizer run for deployment. A failed verification leaves the cost result
visible for diagnosis but blocks deployment preparation until the same run is
verified or the architecture is recalculated. Opening a saved twin always uses its
newest run; an older selected run is never combined with a newer calculation.
Changing any workload input clears the previous recommendation and requires a new
calculation and verification.

The **Review recommendation** task shows this status compactly. The final
configuration summary lists all seven architecture slots plus any required storage
transition or cross-cloud runtime components under **Resolved cloud resources**.
Provider values are read-only. Expand **Show technical evidence** to inspect the
full specification digest, formula and catalog references, classifications, and
Terraform targets. Progressive usage tiers, account-level plans, and calculation
assumptions are explicitly distinguished from values that Terraform can enforce.

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

The Processing task shows **Integrate Error Handling** as unavailable for the
current five-layer baseline. Historical configurations that enabled the legacy
field remain visible as **Legacy, not deployable** and must be recalculated
without that field before deployment. This does not disable event checking,
notification workflows, device feedback, or configured event actions.

## Artifacts

Data contracts, user functions, IoT payloads, hierarchy/state-machine files, and scene
assets are validated through typed upload/editor boundaries. Read-only generated views
help inspection; generated deployment files are not independent user-owned truth.
