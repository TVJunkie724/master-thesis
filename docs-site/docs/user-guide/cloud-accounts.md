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

When supported, a transient administrator credential can create a versioned scoped
credential. The generated connection is encrypted and persisted; administrator
plaintext is discarded after the operation. The administrator credential is not a
profile secret and cannot be read back.

## Delete Or Replace

Deletion is blocked when a deployment connection is still referenced. Unbind/replace
it first. Removing a pricing default disables refresh for that provider until another
default is selected. Existing historical refresh/calculation records remain evidence.
