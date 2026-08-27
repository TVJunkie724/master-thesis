# Azure Setup

Use an existing billing-enabled subscription and a non-root service principal.
Import its JSON or enter tenant, subscription, client ID and secret through the
write-only form. Verify the returned principal and subscription before binding
the connection.

The application may propose registration of exact graph-required Azure
resource providers. Registration is shown before execution, requires explicit
confirmation, is idempotent, and remains a shared subscription prerequisite
after Twin Destroy.

Microsoft Graph permissions/consent, quota increases, organization policy,
subscription creation, billing recovery, legal/preview approval, and
provider-side credential lifecycle remain manual. Readiness reports those
conditions as typed external blockers rather than attempting broad tenant
administration.
