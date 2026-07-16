# UIBK SAML Authentication

This component note documents the Management API implementation. The canonical
operator and user documentation is the docs-site page
`docs-site/docs/runtime/authentication.md`.

## Implemented Boundary

UIBK authentication is SP-initiated SAML 2.0:

```text
Flutter -> POST /auth/providers/uibk/login
        <- auth URL + transaction ID + poll verifier
browser -> UIBK IdP
UIBK IdP -> POST /auth/uibk/callback
Management API -> verify signature, InResponseTo, RelayState, NameID, mail
Flutter -> POST /auth/session/exchange
        <- revocable JWT + current user
```

The callback never redirects a token to Flutter. `RelayState` is an opaque,
one-time browser state whose digest is stored in `auth_login_transactions`.
The SAML request ID is stored with that transaction and supplied to
`process_response`; unsolicited or replayed callbacks fail. Flutter holds a
different poll verifier and can consume the completed result once.

## Required Configuration

```dotenv
SAML_ENABLED=true
SAML_SP_ENTITY_ID=https://twin2multicloud.example/service-provider
SAML_ACS_URL=https://api.twin2multicloud.example/auth/uibk/callback
SAML_SP_CERT=<PEM certificate content expected by python3-saml>
SAML_SP_KEY=<PEM private-key content expected by python3-saml>
SAML_IDP_ENTITY_ID=<registered UIBK IdP entity ID>
SAML_IDP_SSO_URL=<registered UIBK SSO endpoint>
SAML_IDP_CERT=<current UIBK IdP signing certificate>
```

Production startup rejects an incomplete tuple, a non-HTTPS ACS URL, or
`SAML_ENABLED=true` without the `python3-saml` runtime dependency. Provider
secrets/keys must be supplied through the deployment secret boundary; they
must not be committed or compiled into Flutter.

`GET /auth/uibk/metadata` returns the configured SP metadata with `no-store`
only while SAML is enabled. Submit that exact metadata to the institutional
registration process; do not hand-edit a second copy.

## Identity Contract

Required assertion values:

| Value | Use |
|---|---|
| NameID | immutable external identity subject |
| `mail` or its standard OID | normalized profile email |
| `displayName` or `cn` | optional display name |

The unique identity key is `(uibk, NameID)`. Email never auto-links accounts.
If the email belongs to an existing user with another provider identity, the
flow returns `IDENTITY_LINK_REQUIRED` until an explicit account-linking feature
exists.

## External Activation Gate

Live UIBK authentication cannot be completed from source code alone. GitHub
issue `#49 Document and resolve UIBK login prerequisites` tracks the required
UIBK/ACOnet coordination:

1. stable public HTTPS API domain;
2. approved SP entity ID and exact ACS URL;
3. SP certificate ownership, storage, rotation, and expiry procedure;
4. current IdP metadata/entity/SSO/signing certificate;
5. release of NameID, `mail`, and optional display-name attributes;
6. test identity and federation registration/approval;
7. privacy, support, and logout expectations.

Localhost is not a production ACS. Until this gate is complete,
`GET /auth/providers` reports UIBK unavailable and Flutter does not attempt it.

## Verification

```bash
docker --context orbstack compose run --rm management-api \
  python -m pytest -q tests/test_auth_providers.py tests/test_auth_routes.py
```

The deterministic suite verifies SAML request correlation, stable subject and
email extraction, missing/invalid attributes, callback replay rejection,
one-time exchange, and disabled capability behavior. A supervised live IdP
test is still required after institutional activation.
