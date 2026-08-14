# Configuration Workspace

The workspace replaces one long three-page form with six focused phases and smaller tasks.
The sidebar provides orientation, completion/attention status, and direct access to
navigable tasks; blocked tasks explain their prerequisite.

## Phases And Tasks

| Phase | Tasks |
|---|---|
| Define twin | identity and mode |
| Architecture | select profile, understand architecture |
| Workload | scenario/currency, device traffic, processing, retention, twin capabilities |
| User Logic | bind profile-required user logic |
| Optimize and review | pricing readiness, calculate alternatives, compare and select |
| Deployment review | cloud access, data contracts, twin assets, summary, readiness findings, validation/preflight |

The conceptual phases replace the old UX, but typed backend contracts retain legacy
step projections internally where needed for compatibility.

## Dependency Rules

```text
twin identity
   -> active profile selected and its logical flow visited
      -> complete workload and required user logic
      -> pricing ready enough to calculate
         -> calculation result / verified deployment selection
            -> required provider cloud access
               -> deployment artifacts
                  -> validation and preflight
```

Users may revisit completed tasks. A material configuration edit can invalidate a
calculation, readiness result, or `configured` state. The workspace shows the next
recommended task rather than pretending downstream results remain current.

The active profile list is owned by Management. Its current runtime catalog
contains Five-layer v2 and Six-layer v1; historical Five-layer v1 Twins remain
readable but are not selectable for new work. The earlier Phase 8.7 empty
catalog was an activation seam, not a disabled or “coming soon” UI. A profile
change first shows the exact server-calculated workload, user-logic, run, and
readiness invalidations and requires explicit confirmation.

## First Real-Provider Lifecycle

No cloud preparation is required before creating a draft Twin or calculating
an offline architecture. Real deployment access follows this exact current PoC
boundary:

1. Outside the app, create or select the provider account/subscription/project,
   enable billing where required, and obtain temporary owner/admin bootstrap
   authority.
2. Start the UI and create/configure/calculate the Twin without that authority.
3. Resolve the selected providers in **Prepare deployment -> Cloud access**.
   The in-app deterministic adapters are offline only. For a real provider,
   request the reviewed manual bootstrap plan, authenticate through the
   provider CLI, inspect the dry run, and apply it explicitly.
4. Import and validate only the generated bounded `thesis-demo-v2`
   CloudConnection. Bind it to the Twin; the initial owner/admin credential is
   neither imported nor retained by the app.
5. Revoke or delete the temporary owner/admin authority and complete any
   provider-side manual cleanup before acknowledging it in the workflow.
6. Run Twin deployment preflight. Complete only the exact account-level,
   billing, quota, policy, AWS Identity Center, or GCP OAuth prerequisite the
   preflight reports, then recheck through the bounded connection.
7. Deploy only in a separately approved supervised run. After successful live
   verification, Twin Overview can expose the generated L4 semantic-Twin and
   L5 Grafana links with their provider-owned access instructions.

The repository's offline evaluation and default tests stop before steps 3-7
perform any provider mutation. They do not produce live links or credentials.

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
