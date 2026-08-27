# Authentication boundary

The thesis PoC is a single-user, locally operated system. It does not claim
production identity federation, roles, multi-tenancy or public Internet
deployment.

Development mode uses one explicit local sign-in action and a configured
development bearer accepted only by the local Management API. Demo mode uses a
fixture identity and performs no network calls. Provider CloudConnections are
not application-login credentials.

For supervised evaluation, run the application in an isolated environment,
restrict network access to the operator and protect the local signing and
encryption keys. Never expose the development bearer as a general login or use
it as evidence of production authentication.

Google OAuth, university SAML, role management, shared rate-limit storage and
production session operations are outside the final PoC scope. Their historical
implementation is not part of the supported thesis workflow.
