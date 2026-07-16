# Authentication

Authentication is profile-specific. Development and demo are complete local
capabilities; production identity is not yet enabled in Flutter.

## Current Profile Behavior

| Profile | User experience | Backend behavior |
|---|---|---|
| development | explicit **Continue in local development** action | bearer token accepted only when `DEV_AUTH_ENABLED=true` in development/test |
| demo | fixture identity, no login network call | no backend |
| production | UIBK and Google buttons shown disabled with a configuration notice | OAuth/SAML routes exist but are not yet a production-ready end-to-end client flow |

## Google OAuth Boundary

Backend settings:

- `GOOGLE_CLIENT_ID`;
- `GOOGLE_CLIENT_SECRET`;
- `GOOGLE_REDIRECT_URI`;
- `FRONTEND_CALLBACK_URL`.

The backend can initiate OAuth, validate one-time in-memory state, exchange the code,
create/find a user, and redirect with a JWT. This is not exposed as an enabled
production Flutter flow. Multi-replica state storage, callback token transport, account
linking policy, and client callback handling need the production-auth hardening issue.

## UIBK SAML Boundary

Backend settings:

| Setting | Meaning |
|---|---|
| `SAML_ENABLED` | explicit capability gate |
| `SAML_SP_ENTITY_ID` | registered service-provider entity ID |
| `SAML_ACS_URL` | HTTPS assertion consumer endpoint `/auth/uibk/callback` |
| `SAML_SP_CERT`, `SAML_SP_KEY` | service-provider signing certificate/key material |
| `SAML_IDP_ENTITY_ID`, `SAML_IDP_SSO_URL`, `SAML_IDP_CERT` | federation IdP metadata |

The backend exposes `/auth/uibk/metadata` for service-provider metadata and uses HTTP
Redirect for login plus HTTP POST for the assertion callback. It requires `mail` and a
NameID; display name may come from `displayName` or `cn`.

## External UIBK/ACOnet Prerequisites

Before live activation, the operator must coordinate with the UIBK ZID/IT identity team
and the applicable ACOnet/eduID.at federation process to obtain or confirm:

1. a stable public HTTPS Management API domain;
2. the final SP entity ID and exact ACS URL;
3. SP certificate lifecycle and secure private-key provisioning;
4. IdP metadata/entity/SSO endpoint and current signing certificate;
5. released attributes (`mail`, NameID, and optional display name);
6. federation registration/approval and test identity procedure;
7. logout, support, privacy, and account-linking expectations.

UIBK will not accept localhost as the production ACS URL.

## Required Hardening Before Enablement

The existing backend is a prepared thesis boundary, not a finished production auth
system. Before enabling it:

- replace process-local OAuth/SAML state with expiring shared or durable state;
- validate replay/session behavior and proxy-derived scheme/host handling;
- replace JWT-in-query redirect transport with a safer client session exchange;
- define provider identity/account-linking rules instead of automatic email linking;
- configure secure cookie/token storage and logout/expiry in Flutter;
- add negative callback, replay, signature/certificate, multi-instance, and E2E tests;
- enable Flutter buttons only from an authenticated provider-capability contract.

This work is tracked by GitHub issues `#10` and `#49`. Until those gates are complete,
production sign-in remains visibly unavailable rather than falling back to a dev token.
