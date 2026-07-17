# Testing And Quality Gates

## Safe Default Matrix

| Project | Default verification | Cloud mutation |
|---|---|---:|
| Management API | `./thesis.sh test backend` | no |
| Flutter | `./thesis.sh test frontend` | no |
| Flutter integration | `./thesis.sh test frontend-integration` | no; read-only local stack |
| Optimizer | container `pytest tests/ -v` | no live refresh by default |
| Deployer | container `pytest tests/ --ignore=tests/e2e -v` | no |
| Documentation | strict MkDocs build + link checks | no |

Current suites contain route/contract, unit, integration, security, migration, widget,
architecture, demo, and build coverage. File count is not a quality metric; important
boundaries require success, rejection, ownership, malformed-input, and downstream-error
cases.

## Python Security/Quality

Service images include development requirements for pytest and static/security checks.
Bandit and Ruff findings must be evaluated in context; suppressions require a local,
specific reason. Secret-redaction tests deliberately inject secret-like values into
downstream messages and prove they do not persist or return.

## Flutter Gate

The root frontend test command runs architecture checks, formatting, `flutter analyze`,
unit/widget/demo tests, and Web plus current-host desktop build checks. Native CI
additionally builds macOS, Windows, and Linux releases. UI tests should cover long
text, loading/empty/error states, disabled controls, and representative screen sizes.

The frontend integration command restarts the bind-mounted local services before
executing its read-only checks, so cached OpenAPI documents cannot hide source/runtime
drift. It also compares the Management API optimizer-input contract with the live
Optimizer contract field by field; Flutter still communicates only with the Management
API in application runtime.

A build on one desktop operating system is not evidence for another. The
repository workflow is the authoritative cross-platform compilation gate; see
[Supported Platforms](../getting-started/supported-platforms.md).

## E2E Safety

Do not run provider E2E automatically. A live test plan must specify account/project,
region, expected resources, cost exposure, cleanup/destroy proof, credentials, and
evidence capture. Pricing API reads may be free at request time but can still require
credentials/quotas and are not deterministic unit tests.

## Documentation Gate

```bash
docker compose --profile docs run --rm docs mkdocs build --strict
```

Additionally verify internal links/assets, documented `thesis.sh` commands, Compose
configuration, present-vs-planned wording, and absence of secret values.
