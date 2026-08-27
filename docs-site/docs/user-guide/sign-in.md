# Sign in

## Local development and evaluation

Start the stack with `./thesis.sh up`, then choose **Continue in local
development**. The application uses the bearer from the ignored
`config/dev.json` and creates or loads the single local PoC user.

The bearer is a local convenience, not a production login. Run supervised live
evaluation only in an isolated environment accessible to the operator.

## Offline demo

`./thesis.sh demo` uses a fixture identity, no backend and no network request.
Restarting resets the in-memory state.

External OAuth/SAML providers and multi-user account lifecycle are outside the
supported thesis scope. Provider CloudConnections are deployment authority and
must never be pasted into the sign-in flow.
