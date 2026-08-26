# Cloud Accounts

Cloud Accounts are encrypted, user-scoped CloudConnections. The UI shows only
non-secret metadata: provider, display name, purpose, account/project scope,
validation status, and last use/validation.

## Purposes

| Purpose | Used for |
|---|---|
| deployment | provider preflight and infrastructure deployment for a bound Twin |
| pricing | account-level AWS/GCP price refresh; one default per user/provider |

For the PoC, the same preconfigured administrator credential may be registered
for both purposes. Azure catalog pricing uses the public pricing API.

## Register a connection

1. Create a non-root administrator credential in an isolated thesis cloud
   environment outside the application.
2. Choose provider and purpose in **Settings -> Cloud Accounts & Access**.
3. Submit the credential through the write-only form and verify the displayed
   provider scope.
4. Validate the stored connection.
5. Set it as the pricing default or bind it to a Twin.

The API returns metadata and validation results, never the stored plaintext
payload. Secret values must not be copied into logs, issue bodies, screenshots,
or committed configuration.

Twin2MultiCloud does not create identities, derive permission packs, or rotate
credentials. Revoke or replace the credential directly with the provider after
the supervised deploy/verify/destroy experiment.
