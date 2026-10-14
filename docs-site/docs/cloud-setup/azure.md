# Azure Setup

Azure uses one service principal for this isolated thesis PoC. The same
administrator creates and destroys resources, creates Twin-scoped role
assignments and performs the Microsoft Graph operations required by directed
federation. This intentionally favors a short, reproducible setup over
production least privilege.

## 1. Create the administrator

Use an existing isolated, billing-enabled subscription and its Microsoft Entra
tenant.

1. In **Microsoft Entra ID → App registrations**, create one application.
2. Under **Certificates & secrets**, create one client secret. Copy its value
   when it is shown; never add it to the repository or documentation.
3. Sign in once with an operator who can create subscription role assignments
   and grant tenant-wide Microsoft Graph application consent.
4. From that supervised session, assign the built-in **Owner** role at the
   isolated subscription scope and add these Microsoft Graph **application**
   permissions:
   - `Application.ReadWrite.All`
   - `AppRoleAssignment.ReadWrite.All`
5. Grant admin consent, verify the application credential, then sign out and
   remove the temporary operator session.

Subscription Owner does not grant Microsoft Graph directory permissions. The
two consented application permissions are therefore checked separately. The
one-time operator session may apply the exact role and consent grants
programmatically, but the PoC application cannot grant them to itself.

## 2. Enter or import the credential

In **Settings → Cloud access → Azure** use either path:

- **Enter manually:** subscription ID, tenant ID, Regions, client ID and client
  secret.
- **Import JSON:** select a standard Azure service-principal JSON or the
  allowlisted Twin2MultiCloud compatibility JSON.

The inline **Accepted Azure JSON formats** help shows placeholder-only examples.
A standard file has this form:

```json
{
  "appId": "<administrator-client-id>",
  "password": "<administrator-client-secret>",
  "tenant": "<tenant-id>",
  "subscriptionId": "<subscription-id>"
}
```

The compatibility form may be the direct Azure object or an `azure` member:

```json
{
  "azure": {
    "azure_subscription_id": "<subscription-id>",
    "azure_tenant_id": "<tenant-id>",
    "azure_client_id": "<administrator-client-id>",
    "azure_client_secret": "<administrator-client-secret>",
    "azure_region": "westeurope"
  }
}
```

Known optional IoT Hub and Digital Twins Region fields are accepted. The client
parses the file locally, ignores known AWS/GCP members and retired Azure
preparation fields, and uploads only normalized Azure administrator data.
Credential values are never previewed or returned.

## 3. Validate before a run

Readiness must confirm:

1. the service principal authenticates in the intended tenant and subscription;
2. subscription Owner authority is present;
3. both required Microsoft Graph application permissions are consented;
4. the selected Regions, resource providers, quotas, capacity and L4/L5
   prerequisites are ready or explicitly deferred by the protocol.

Resource-provider registration may be proposed as a bounded, reviewed
preparation plan. Quota increases, policy exemptions, billing repair and
credential creation remain manual. Graph consent is a one-time supervised
operator bootstrap and is never an automatic deployment or UI action.

## Cleanup and revocation

After every run, Destroy Twin-owned resources and inspect residual inventory.
Twin Destroy does not remove the administrator app registration, subscription
Owner assignment, Graph consent, client secret or shared provider
registrations. After the final evaluation, unbind and delete the
CloudConnection, remove the role assignment, revoke Graph consent and delete or
disable the secret and app registration.

See the official [Azure references](provider-links.md#azure).
