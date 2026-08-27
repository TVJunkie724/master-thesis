# Google Cloud Setup

Use an existing billing-enabled GCP project and a non-root service-account key.
Import the service-account JSON or enter its fields through the write-only
form. Verify the returned service-account identity and project before binding
the connection.

The application may propose enabling only APIs required by the resolved graph.
The plan is shown before execution, requires explicit confirmation, is
idempotent, and remains a shared project prerequisite after Twin Destroy. The
PoC does not create a project automatically.

Project creation, billing attachment/recovery, quota approval, organization
policy, OAuth/IAP consent configuration, legal/preview approval, and key
rotation/revocation remain manual. Graph readiness distinguishes these
external blockers from preparable API enablement.
