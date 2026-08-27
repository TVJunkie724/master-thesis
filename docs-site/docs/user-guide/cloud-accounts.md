# Cloud Accounts

Cloud Accounts are encrypted, user-scoped deployment CloudConnections. The UI
shows only provider, display name, authentication kind, account/project scope,
and validation/readiness metadata.

Users may keep several named connections per provider and select the suitable
one for each Twin. There is no pricing-purpose connection or default pricing
credential.

## Add a connection

1. Create a non-root administrator credential in an isolated thesis cloud
   scope outside the application.
2. Enter it in the write-only form or import the supported provider file.
3. Review the detected provider identity and target scope.
4. Run identity validation.
5. Bind the connection to a Twin only when its resolved graph needs that
   provider.

Supported file shapes are AWS access-key CSV, Azure service-principal JSON,
and GCP service-account JSON. Files are parsed as credential input, not stored
as portable Twin artifacts.

Readiness may reveal missing permissions or external provider prerequisites.
Confirm only bounded preparation shown by the application; otherwise follow
the typed manual instruction or replace the connection.

Twin2MultiCloud does not create, minimize, rotate, or revoke the provider
administrator. Revoke it directly with the provider after the experiment.
