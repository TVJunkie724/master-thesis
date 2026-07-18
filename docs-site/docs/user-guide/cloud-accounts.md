# Cloud Accounts

Cloud Accounts are represented by encrypted, user-scoped CloudConnections. The profile
screen shows non-secret metadata: provider, display name, account/project scope,
purpose, permission-set version, validation status, and last use/validation.

## Purposes

| Purpose | Scope | Used for |
|---|---|---|
| deployment | reusable and bindable to twins | provider preflight and infrastructure deployment |
| pricing | one default per user/provider | account-level provider pricing refresh |

The same provider account may require separate credentials because pricing discovery
and infrastructure deployment have different permissions.

## Create Or Import

1. choose provider and purpose;
2. supply the provider credential payload through the secure form/file boundary;
3. verify displayed cloud scope before submission;
4. validate the stored connection;
5. set it as pricing default or bind it to a twin where applicable.

The API returns metadata and validation results, never the stored plaintext payload.

## Bootstrap A Scoped Connection

The current bootstrap is a manual, versioned static-script workflow:

1. request the provider bootstrap plan through the authenticated Management API;
2. review the returned dry-run command and cloud scope;
3. authenticate through the provider CLI outside the application;
4. run the script without `--apply`, review its plan, then apply explicitly;
5. store its generated deployment CloudConnection JSON only in an ignored local path;
6. import that generated connection and validate it before binding it to a twin.

The Management API never receives or persists the administrator credential. Current
bootstrap scripts create deployment identities only. AWS and GCP pricing connections
are created/imported separately; Azure pricing uses its public API path.
Flutter does not currently expose the bootstrap plan/import workflow, so operators use
the Management OpenAPI/HTTP boundary for these two steps.

See [Cloud Setup](../cloud-setup/index.md) for provider-specific commands and security
rules.

## Delete Or Replace

Deletion is blocked when a deployment connection is still referenced. Unbind/replace
it first. Removing a pricing default disables refresh for that provider until another
default is selected. Existing historical refresh/calculation records remain evidence.
