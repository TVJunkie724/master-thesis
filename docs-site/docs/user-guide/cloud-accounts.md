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

Provider owner/admin authority is created or obtained outside the application;
the app cannot create the initial root/owner credential from nothing. Creating
a Twin, choosing a profile, entering the frozen workload, and calculating an
offline result need no cloud credential.

The shared guided flow is available from **Settings -> Cloud Accounts &
Access** and **Prepare deployment -> Cloud access**:

1. choose provider and safe account/subscription/project target;
2. review the provider-owned preparation steps and the bootstrap/deployment
   permission packs;
3. create the safe owner-scoped session;
4. submit the temporary provider credential once;
5. inspect the returned bounded `thesis-demo-v2` deployment connection and the
   distinct local-release/provider-revocation state;
6. complete and explicitly acknowledge manual provider cleanup when requested;
7. from Prepare deployment, continue with the separate Twin preflight.

The credential exists only in the synchronous execute request. It is never
restored into Flutter state or persisted by Management. Resume, cancel,
recheck, start-new, and credential re-entry remain available without claiming
that local release equals provider revocation.

The local PoC guided flow accepts only deterministic test authority and creates
no live cloud identity or resource. Production adapters are disabled, so a real
owner/admin credential must not be pasted into the current guided UI. For
supervised live-provider work,
the compatible manual, versioned static-script workflow remains available:

1. request the provider bootstrap plan through the authenticated Management API;
2. review the returned dry-run command and cloud scope;
3. authenticate through the provider CLI outside the application;
4. run the script without `--apply`, review its plan, then apply explicitly;
5. store its generated deployment CloudConnection JSON only in an ignored local path;
6. import that generated connection and validate it before binding it to a twin.

After the bounded deployment identity is validated and imported, the original
owner/admin credential is no longer used by Twin calculation or normal
deployment preflight. Revoke or delete it according to the provider-side plan;
do not claim completion until any required manual cleanup is actually done.

The manual `plan`/`import` endpoints never receive the administrator credential;
authentication remains in the provider CLI. Current bootstrap scripts create
deployment identities only. AWS and GCP pricing connections are created/imported
separately; Azure pricing uses its public API path.

See [Cloud Setup](../cloud-setup/index.md) for provider-specific commands and security
rules.

## Delete Or Replace

Deletion is blocked when a deployment connection is still referenced. Unbind/replace
it first. Removing a pricing default disables refresh for that provider until another
default is selected. Existing historical refresh/calculation records remain evidence.
