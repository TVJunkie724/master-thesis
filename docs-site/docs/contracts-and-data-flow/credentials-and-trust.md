# Credentials and Trust

Twin2MultiCloud accepts pre-existing, non-root deployment authority for isolated
thesis accounts, subscriptions, or projects. It does not create, rotate, or
revoke provider credentials.

AWS and Google Cloud each use one provider principal. Azure stores two distinct
principals in one deployment-purpose CloudConnection: a deployment principal for
ordinary resource CRUD and a preparation principal for exact conditional RBAC
assignments and graph-required Entra objects. This is a bounded Azure exception,
not a generic credential-purpose registry.

## Runtime flow

1. The operator enters or imports AWS access-key CSV, Azure deployment
   service-principal JSON plus typed preparation fields, or GCP service-account
   JSON through a write-only request.
2. Management validates the allowlisted shape, encrypts the complete payload, and
   returns only safe configured flags and non-secret scope metadata.
3. The user may retain several named connections per provider and explicitly bind
   one required connection per provider to a Twin.
4. Identity validation verifies each principal and its target scope. Azure checks
   deployment ARM authority, conditional preparation RBAC, and Microsoft Graph
   application permissions independently.
5. Graph-derived readiness sends plaintext only to the Deployer for that request.
   Terraform uses the Azure deployment principal by default and the preparation
   alias only for role assignments and Entra operations.
6. Missing preparable capabilities produce a reviewed, digest-bound plan;
   external blockers produce typed manual or connection-replacement guidance.

Replacing either Azure principal changes the one-way credential fingerprint and
invalidates stale readiness evidence. Existing single-principal Azure records
remain readable and deletable, but cannot be used for readiness or deployment.

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
