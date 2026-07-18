# Operations And Logging

## Daily Commands

```bash
./thesis.sh up --no-flutter
./thesis.sh status
./thesis.sh logs management-api
./thesis.sh logs 2twin2clouds
./thesis.sh logs 3cloud-deployer
./thesis.sh down
```

Use `--build` after dependency or Dockerfile changes. `--skip-smoke` is a diagnostic
escape hatch, not the normal startup path.

## Log Ownership

| Log type | Owner | Access |
|---|---|---|
| application/container logs | each service | `thesis.sh logs` / Docker logs |
| deployment progress | Deployer, relayed/persisted by Management API | Flutter SSE and deployment history |
| pricing refresh progress | Optimizer, relayed as run state | Flutter pricing review |
| credential security events | Management API | owner-scoped audit API/profile UI |
| data-flow verification results | Deployer, persisted/projected by Management API | twin overview verification UI |

Structured operation contexts include request/session/operation and phase identifiers.
Secrets must be redacted before logs cross a service boundary. A raw provider response
is pricing evidence only when stored through the evidence contract, not an excuse to
log credentials or arbitrary request bodies.

Azure Function HTTP failures return a stable code and, for server-side failures, a
`correlation_id`. Search container/provider runtime logs for that exact identifier.
The matching log contains a bounded redacted diagnostic; the response deliberately
does not expose provider bodies, stack traces, signed URLs, or configuration values.

## Health Versus Readiness

A running process does not prove cloud readiness. Distinguish:

- service health: API responds;
- configuration readiness: required twin inputs exist and validate;
- credential preflight: selected connection satisfies expected provider checks;
- deployment readiness: manifest/artifacts/preflight are current;
- live verification: deployed provider resources and data paths pass probes.

## Recovery

The Management API records operation state independently from twin state. On a failed
deploy/destroy, inspect the operation history, correlated logs, last structured error,
and retained Terraform state before retrying. Do not delete runtime state merely to
make the UI appear ready.
