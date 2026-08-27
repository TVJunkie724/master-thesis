# Dashboard and Twins

The dashboard lists the user's active Twins and their lifecycle state. It is
not a pricing or provider-administration dashboard.

## Twin actions

- create a new draft with a unique name;
- import a typed secret-free Twin archive under a new name;
- open an existing Twin;
- duplicate a Twin into an independent draft;
- edit a draft configuration;
- explicitly Deploy or Destroy when the relevant gates permit it;
- remove an inactive local record after confirmation.

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
