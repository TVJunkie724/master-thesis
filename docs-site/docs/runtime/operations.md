# Operations and Logging

## Local commands

```bash
./thesis.sh up --no-flutter
./thesis.sh status
./thesis.sh logs management-api
./thesis.sh logs 2twin2clouds
./thesis.sh logs 3cloud-deployer
./thesis.sh down
```

These commands operate the local stack. They do not authorize provider
mutations.

## Operation evidence

Deploy and Destroy are durable Management operations. Each has an idempotency
key, correlation ID, bounded persisted progress, replay cursor, and one
authoritative terminal result. Flutter reads persisted history before resuming
SSE, so reconnect does not repeat a provider action.

| Evidence | Owner | User access |
|---|---|---|
| application logs | each service | local container logs |
| provider mutation progress | Deployer, persisted by Management | Flutter operation history and SSE |
| verification result | Deployer, persisted by Management | Twin overview |
| cleanup inventory and residual failures | Deployer, persisted by Management | Destroy result |
| credential security events | Management | owner-scoped diagnostic read |

Logs are bounded and redacted before crossing a service boundary. Provider
responses, payloads, signed URLs, credential values, and stack traces do not
belong in public errors or operation history.

## Health versus evidence

- service health proves only that a process responds;
- configuration validation proves only typed local input;
- identity validation proves the submitted principal and scope;
- graph readiness proves current deployment prerequisites;
- Terraform success proves resources were applied;
- telemetry verification proves the defined functional roundtrip;
- cleanup evidence proves what was removed, retained as shared, or residual.
