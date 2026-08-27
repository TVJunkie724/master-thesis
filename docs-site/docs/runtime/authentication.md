# Authentication boundary

The thesis PoC is a single-user, locally operated system. It does not claim
production identity federation, roles, multi-tenancy or public Internet
deployment.

Development and production-like evaluation modes load one configured PoC
profile through `/auth/me`. A static bearer protects the local Management API;
there is no interactive application sign-in. Demo mode uses a fixture profile
and performs no network calls. Provider CloudConnections are not application
login credentials.

For supervised evaluation, run the application in an isolated environment,
restrict network access to the operator and protect the runtime encryption key.
Never expose the PoC bearer as a general login or use it as evidence of
production authentication.

Google OAuth, university SAML, Microsoft/OIDC login, role management and
production session operations are outside the final PoC scope. The retained
login screen is an unrouted UI seam and contains no provider implementation.
