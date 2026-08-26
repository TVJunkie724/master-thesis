# AWS Setup

Use an isolated AWS thesis account and a preconfigured non-root administrator
credential. Register it as an encrypted CloudConnection and validate the
account with STS before pricing or deployment.

AWS pricing refresh additionally validates the read operations required for
the regional price evidence and the IoT TwinMaker pricing plan. Deployment
preflight checks the real operations required by the selected Six-layer graph.
The PoC does not derive an IAM policy or create/rotate access keys.

Static checks and mocked provider tests are implemented. Real refresh,
deploy, verification, destroy, and credential revocation remain supervised
live gates.
