# Credentials and Trust

Twin2MultiCloud accepts pre-existing, non-root deployment authority for isolated
thesis accounts, subscriptions, or projects. It does not create, rotate, or
revoke provider credentials.

Each CloudConnection stores one provider principal. Azure uses one
subscription administrator for resource CRUD, RBAC assignments and
graph-required Entra objects. This is an isolated thesis-PoC simplification,
not a production least-privilege claim or generic identity-governance model.

## Runtime flow

1. The operator enters or imports AWS access-key CSV, Azure administrator
   service-principal JSON, or GCP service-account JSON through a write-only
   request.
2. Management validates the allowlisted shape, encrypts the complete payload, and
   returns only safe configured flags and non-secret scope metadata.
3. The user may retain several named connections per provider and explicitly bind
   one required connection per provider to a Twin.
4. Identity validation verifies each principal and its target scope. Azure checks
   subscription Owner authority and Microsoft Graph application permissions
   independently.
5. Graph-derived readiness sends plaintext only to the Deployer for that request.
   Terraform uses the same Azure administrator for resources, role assignments
   and Entra operations.
6. Missing preparable capabilities produce a reviewed, digest-bound plan;
   external blockers produce typed manual or connection-replacement guidance.

Replacing the Azure administrator changes the one-way credential fingerprint
and invalidates stale readiness evidence. Retired preparation fields from old
encrypted records are dropped before the Deployer boundary.

## Secret exit rules

| Boundary | Allowed | Forbidden |
|---|---|---|
| CloudConnection response | provider, label, auth kind, configured booleans, validation state | client IDs, credential values, private keys |
| encrypted store | ciphertext and owner-safe metadata | plaintext persistence |
| Deployer request | request-scoped typed provider bundle | retry, event, or log copies |
| Terraform input | request-local sensitive variables | manifests, outputs, plans in evidence |
| archives and evidence | connection IDs or one-way fingerprints where needed | secrets, tokens, private keys |
| Flutter state | labels, readiness, and repair guidance | retained submitted credential material |

Supported preparation may register required Azure resource providers and enable
required GCP APIs only after confirmation. Other account-level changes remain
manual. A Twin Destroy removes Twin-owned resources but does not undo shared
provider capabilities, provider IAM/RBAC/Graph configuration, or credentials.
