# Sign in

## Local development and evaluation

Start the stack with `./thesis.sh up`. The application uses the bearer from the
ignored `config/dev.json` to create or load the configured local PoC profile and
opens the dashboard directly. There is no routed sign-in step.

The bearer is a local convenience, not a production login. Run supervised live
evaluation only in an isolated environment accessible to the operator.

## Offline demo

`./thesis.sh demo` uses a fixture identity, no backend and no network request.
Restarting resets the in-memory state.

External OAuth/SAML/OIDC providers and multi-user account lifecycle are outside
the supported thesis scope. Provider CloudConnections are deployment authority
and must never be used as application-login credentials.
