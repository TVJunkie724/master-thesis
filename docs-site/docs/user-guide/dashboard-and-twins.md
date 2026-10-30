# Twin experiments

The **Twin experiments** screen starts or resumes one thesis scenario. It lists
the Twin name, lifecycle state and latest update. It is not a pricing,
analytics or provider-administration dashboard.

## Twin actions

- use **New Twin** to create a draft with a unique name;
- use **Import Twin** to import a typed secret-free archive under a new name;
- use **Continue configuration** for a draft;
- use **Open lifecycle** for every non-draft state;
- use the row menu to Duplicate a Twin into an independent draft or to Export
  its portable archive;
- explicitly Deploy or Destroy when the relevant gates permit it;
- use the row menu to remove a non-deployed local record after confirmation.

Delete is blocked while a Twin is deployed. Open its lifecycle, run Destroy
and verify cleanup first. The list has no filters or user-defined sorting; the
latest updated experiment appears first.

All Twins use the same canonical Six-layer contract. There is no architecture
profile or optimization-objective selector.

## Immutability

A deployed Twin cannot be edited in place. Duplicate it, change the new draft,
run a new calculation, and deploy it independently. The source Twin remains
active until the user explicitly destroys it; the application never removes it
as a side effect of duplication.

The Twin overview shows the configuration summary, immutable cost/graph
evidence, connection/readiness state, operations, verification, access bundle,
and cleanup result relevant to that Twin.
