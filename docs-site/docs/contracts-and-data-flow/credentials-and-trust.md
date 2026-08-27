# Credentials and Trust

Twin2MultiCloud accepts pre-existing, non-root deployment administrator
credentials for isolated thesis accounts, subscriptions, or projects. It does
not create, minimize, rotate, or revoke that authority.

## Runtime flow

1. The operator enters or imports AWS access-key CSV, Azure service-principal
   JSON, or GCP service-account JSON through a write-only request.
2. Management validates the file shape, encrypts the payload, and returns only
   non-secret identity/scope metadata.
3. The user may keep several named connections per provider and explicitly
   bind the required ones to a Twin.
4. An identity probe verifies the principal and target scope.
5. Graph-derived readiness sends the secret only to the Deployer for the
   current request.
6. Missing preparable capabilities produce a reviewed, digest-bound plan;
   external blockers produce typed manual instructions or a connection
   replacement path.

## Secret exit rules

| Boundary | Allowed | Forbidden |
|---|---|---|
| CloudConnection response | provider, label, auth kind, account/project metadata, validation state | credential values |
| encrypted store | ciphertext and owner-safe metadata | plaintext persistence |
| Deployer request | request-scoped typed credential | retry/event/log copies |
| archives and evidence | connection IDs/fingerprints where needed | secrets, tokens, private keys |
| Flutter state | labels, scope, readiness and repair guidance | submitted credential material |

Supported preparation may register required Azure resource providers and enable
required GCP APIs after confirmation. Other account-level changes remain
manual. A Twin Destroy removes Twin-owned resources but does not undo shared
provider capabilities or revoke the administrator credential.
