# Troubleshooting

## Calculation fails

Confirm that the Twin uses the canonical contract, the workload is schema
valid, required bounded extensions are valid/bound, and all exact frozen
pricing references pass digest validation. There is no live price refresh or
alternate profile to select.

## CloudConnection validation fails

Check the imported file shape, principal identity, account/subscription/project
scope, and whether the credential is still active. Replace the named
connection if necessary; never paste secrets into logs or issue text.

## Readiness is incomplete

Read each typed finding and its graph requirement ID:

- confirm a supported bounded preparation plan when offered;
- follow the provider-specific manual instruction for billing, quota, policy,
  consent, legal, or capacity blockers;
- replace the connection when its authority is insufficient;
- rerun readiness after any change.

A service health check or old successful validation does not satisfy current
graph readiness.

## Deploy/Destroy stream disconnects

Reload the Twin overview. Management returns persisted operation progress and
the client resumes after the last cursor. Do not start a second operation merely
because the stream disconnected.

## Deployment fails

Inspect the correlation ID, bounded phase error, operation history, retained
Terraform state, and current provider inventory. A failed deploy may still
have created resources, so explicit cleanup remains available when evidence
requires it.

## Destroy is incomplete

Use cleanup evidence to distinguish retained shared prerequisites from genuine
residual failures. Record and remove residual billable resources under
supervision; never delete state simply to make the UI appear clean.

## Access link does not open

Check the access bundle's provider, authentication kind, assigned identity,
readiness, expiry, and network restriction. Browser authentication remains a
provider-owned external step. Twin2MultiCloud does not create a generic login
or administer the linked dashboard.
