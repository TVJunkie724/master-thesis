# Azure Setup

Azure is the only provider in this PoC that needs two service principals. They
share one tenant and subscription but have non-overlapping responsibilities and
are stored as one encrypted Azure access bundle.

| Principal | Purpose | Must not have |
|---|---|---|
| deployment | create, verify, and Destroy ordinary Azure resources | role-assignment mutation or Microsoft Graph administration |
| preparation | create/delete only approved role assignments; create graph-required Entra objects | ordinary resource write/delete authority, Owner, Contributor, or unrestricted delegation |

## 1. Create the two app registrations

Use an existing isolated, billing-enabled subscription and its Microsoft Entra
tenant.

1. In **Microsoft Entra ID → App registrations**, create one application for the
   deployment principal and one for the preparation principal.
2. Create one client secret for each application. Record each secret value when
   it is shown; do not copy it into the repository or documentation.
3. Keep the two application/client IDs distinct. Both principals must authenticate
   against the same tenant and subscription.
4. Assign the built-in **Contributor** role to the deployment principal at the
   isolated subscription scope. Do not assign Owner or an additional custom
   deployer role. Contributor covers ordinary Six-layer resource CRUD while its
   built-in exclusions prevent role-assignment mutation.

Azure Digital Twins data access is not a subscription prerequisite. During an
approved atomic Apply, the preparation principal grants **Azure Digital Twins
Data Owner** to the deployment principal only on the newly created Twin
instance. That binding is removed with the Twin.

## 2. Constrain the preparation principal

At the isolated subscription scope, assign **Role Based Access Control
Administrator** to the preparation principal. In the role assignment's
**Conditions** tab choose the option that allows only selected roles to selected
principal types.

Permit only `User` and `ServicePrincipal` targets and exactly these role names:

- `AcrPull`
- `Azure Digital Twins Data Owner`
- `Azure Digital Twins Data Reader`
- `Azure Event Hubs Data Receiver`
- `Azure Event Hubs Data Sender`
- `Azure Service Bus Data Receiver`
- `Azure Service Bus Data Sender`
- `Grafana Admin`
- `Grafana Viewer`
- `IoT Hub Data Contributor`
- `IoT Hub Data Reader`
- `Storage Blob Data Contributor`
- `Reader` for the approved identity-only Phase 8 probes

Do not permit group targets or any other role. In particular, do not grant Owner,
Contributor, User Access Administrator, or an unrestricted Role Based Access
Control Administrator assignment.

## 3. Add the exact Microsoft Graph application permissions

On the **preparation** app registration, add these Microsoft Graph **application**
permissions and no broader replacement:

1. `Application.ReadWrite.OwnedBy`
2. `Application.Read.All`
3. `AppRoleAssignment.ReadWrite.All`

A tenant administrator must grant admin consent in the Azure portal. The PoC
validates that the exact permissions are consented, but it never grants consent.
These permissions are required only for the ephemeral Entra applications,
service principals, federated credentials, and app-role assignments used by the
directed federation probes.

## 4. Enter or import the Azure bundle

In **Settings → Cloud access → Azure**:

- **Enter manually:** subscription ID, tenant ID, Regions, deployment client ID
  and secret, then preparation client ID and secret.
- **Import JSON:** select one standard deployment-principal JSON and enter the
  preparation client ID and secret in the transient typed fields; or select one
  complete Twin2MultiCloud compatibility JSON. There is no two-file credential
  archive.

The inline **Accepted Azure JSON formats** help shows both accepted shapes with
placeholders. A standard file has this form:

```json
{
  "appId": "<deployment-client-id>",
  "password": "<deployment-client-secret>",
  "tenant": "<tenant-id>",
  "subscriptionId": "<subscription-id>"
}
```

The complete compatibility form may be the direct Azure object or an `azure`
member in the tracked root object:

```json
{
  "azure": {
    "azure_subscription_id": "<subscription-id>",
    "azure_tenant_id": "<tenant-id>",
    "azure_client_id": "<deployment-client-id>",
    "azure_client_secret": "<deployment-client-secret>",
    "azure_preparation_client_id": "<preparation-client-id>",
    "azure_preparation_client_secret": "<preparation-client-secret>",
    "azure_region": "westeurope"
  }
}
```

Known optional IoT Hub and Digital Twins Region fields are also accepted. The
client parses the selected file locally, prefills the form, ignores known AWS
and GCP root members and sends only normalized Azure deployment-principal JSON
to Management. Secret values are obscured and never previewed. Replacing the
file clears the previous transient values before the replacement is parsed.

The server validates the target scope and identities. Responses show only safe
status metadata; neither client ID nor either secret is returned.

## 5. Validation checkpoints

Before binding the bundle, require all three authority checks to pass separately:

1. deployment resource authority is complete and cannot mutate role assignments;
2. preparation RBAC authority has condition version 2.0, the exact role allowlist,
   and only the allowed principal types;
3. Microsoft Graph exposes exactly the three consented application permissions.

Then confirm subscription state, Regions, resource providers, quotas, capacity,
and L4/L5 prerequisites. Resource-provider registration may be proposed as a
bounded, reviewed preparation plan. Quota increases, policy exemptions, billing,
Graph consent, and credential creation remain manual.

Legacy Azure CloudConnections without the preparation principal remain visible
and deletable but cannot pass readiness. Create a complete bundle, rebind the
draft Twin, and delete the unbound legacy entry.

## Cleanup and revocation

After every run, Destroy Twin-owned resources and inspect residual inventory.
Twin Destroy does not remove app registrations, subscription role assignments,
Graph consent, secrets, or shared provider registrations. After the final
evaluation, unbind and delete the CloudConnection, remove both role assignments,
revoke Graph consent, and delete or disable both secrets and app registrations.

See the official [Azure references](provider-links.md#azure).
