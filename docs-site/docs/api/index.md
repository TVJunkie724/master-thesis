# API

The Management API is the only application boundary used by Flutter. Optimizer
and Deployer APIs are internal contracts.

| Service | Swagger | OpenAPI |
|---|---|---|
| Management | `http://localhost:5005/docs` | `http://localhost:5005/openapi.json` |
| Optimizer | `http://localhost:5003/docs` | `http://localhost:5003/openapi.json` |
| Deployer | `http://localhost:5004/docs` | `http://localhost:5004/openapi.json` |

Protected Management routes use the configured local development bearer. This
is a single-user PoC mechanism, not production authentication.

Deploy and Destroy progress uses SSE backed by durable operation state. Clients
recover from a page or stream interruption by resuming the recorded operation;
they must not issue a second provider mutation.

Internal errors are transformed at the Management boundary into owner-scoped,
redacted responses. Reaching local ports 5003 or 5004 does not make them Flutter
integration points.
