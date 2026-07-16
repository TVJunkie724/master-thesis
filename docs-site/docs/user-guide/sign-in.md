# Sign In

The available sign-in experience depends on how the application was started.

## Development

`./thesis.sh up` starts the local stack and Flutter. Select **Continue in local
development** on the login screen. This deliberate action uses the local token
generated into `twin2multicloud_flutter/config/dev.json`; it is not available
in a production build.

## Offline Demo

`./thesis.sh demo` opens a pre-authenticated fixture user. No browser, backend,
cloud account, or network request is involved. Restarting resets demo state.

## Production

The login screen asks the Management API which external providers are enabled.
Select Google or UIBK, complete authentication in the opened browser, then
return to Twin2MultiCloud. The application waits for the verified result and
continues automatically. The browser callback never asks you to copy a token.

You can cancel while waiting. A cancelled or expired attempt cannot be resumed;
start a new sign-in operation. Logout revokes the server session and returns to
the login screen.

## Availability Messages

| Message/state | Meaning | Action |
|---|---|---|
| no production provider enabled | Management API has no complete provider configuration | contact the deployment operator |
| UIBK unavailable | institutional SAML configuration or runtime dependency is incomplete | use another enabled provider or wait for activation |
| browser could not be opened | the OS/browser blocked the external window | allow popups on Web or retry from the desktop app |
| sign-in request expired | the short-lived transaction elapsed | start again |
| account already exists | the email belongs to another provider identity and was not auto-linked | sign in through the existing provider |
| session expired | token expired, was revoked, or no longer has a server session | sign in again |

Provider credentials, SAML assertions, OAuth codes, and application tokens must
never be pasted into a support ticket or screenshot. Give the operator the
visible request ID from a structured API error instead.

See [Authentication](../runtime/authentication.md) for the protocol, security,
configuration, and external UIBK activation boundary.
