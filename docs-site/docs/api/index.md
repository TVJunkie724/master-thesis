# API

The Management API is the public application boundary. Optimizer and Deployer APIs are
internal contracts used by it.

## Live References

| Service | Swagger UI | OpenAPI JSON |
|---|---|---|
| Management API | `http://localhost:5005/docs` | `http://localhost:5005/openapi.json` |
| Optimizer | `http://localhost:5003/docs` | `http://localhost:5003/openapi.json` |
| Deployer | `http://localhost:5004/docs` | `http://localhost:5004/openapi.json` |

## Authentication

Protected Management API endpoints require a bearer token. Development mode offers an
explicit local token only when enabled. Production expects real OAuth/SAML-issued
application tokens; institutional SAML activation remains externally gated.

## Streaming

Long-running deployment/log workflows use SSE for server-to-client progress. Durable
status/history remains available through REST, so clients recover after stream or page
loss by re-reading operation state.

## Internal API Rule

Optimizer and Deployer ports are published for local development and OpenAPI inspection.
That does not authorize Flutter to call them. Internal contract errors are transformed
at the Management API boundary into owner-scoped, redacted public responses.

See [API and Contracts](../developer-guide/contracts.md) for evolution rules.
