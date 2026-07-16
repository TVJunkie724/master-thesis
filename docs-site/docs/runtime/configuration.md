# Configuration Reference

## Root Entrypoint Variables

| Variable | Default | Purpose |
|---|---|---|
| `THESIS_COMPOSE_PROJECT` | `master-thesis` | isolate Compose names/volumes |
| `THESIS_DOCKER_CONTEXT` | current context | select OrbStack/Docker context |
| `THESIS_PYTHON_COMMAND` | detected `python3` or `python` | optional Python 3 executable override |
| `THESIS_OPTIMIZER_PORT` | `5003` | Optimizer host port |
| `THESIS_DEPLOYER_PORT` | `5004` | Deployer host port |
| `THESIS_MANAGEMENT_API_PORT` | `5005` | Management API host port |
| `THESIS_DOCS_PORT` | `5010` | docs host port |
| `THESIS_API_BASE_URL` | derived from API port | Flutter API origin |
| `THESIS_DEV_AUTH_TOKEN` | `dev-token` | local-only explicit dev token |
| `THESIS_FLUTTER_DEVICE` | detected host desktop | optional Flutter target override (`macos`, `windows`, `linux`, or `chrome`) |
| `THESIS_DEMO_SCENARIO` | `showcase` | offline fixture set |
| `THESIS_RUNTIME_SECRETS_DIR` | `.secrets/runtime` | ignored local runtime keys |
| `THESIS_LOCAL_DATABASE_PATH` | backend app DB | bootstrap/migration guard path |

## Management API

Important groups from `src/config.py`:

| Group | Settings |
|---|---|
| environment | `APP_ENV`, `DEBUG`, `HOST`, `PORT` |
| database | `DATABASE_URL` |
| runtime secrets | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_EXPIRE_MINUTES`, `ENCRYPTION_KEY` |
| authentication lifecycle | `AUTH_TRANSACTION_TTL_SECONDS`, `AUTH_POLL_INTERVAL_MS` |
| authentication limiter | `AUTH_RATE_LIMIT_ENABLED`, `AUTH_RATE_LIMIT_STORAGE_URI`, login/exchange rates |
| identity | complete Google OAuth tuple; SAML enable/entity/ACS/cert/key/IdP tuple |
| transport | `REQUIRE_HTTPS`, `TRUSTED_PROXY_CIDRS`, `CORS_ORIGINS` |
| dev gates | `DEV_AUTH_ENABLED`, `DEV_AUTH_TOKEN`, `ENABLE_TEST_ENDPOINTS`, `SEED_DATA` |
| credential controls | limiter enable/storage and write/validation/bootstrap rates |
| downstreams | `OPTIMIZER_URL`, `DEPLOYER_URL`, preflight max age |
| uploads | `UPLOAD_DIR`, `MAX_GLB_SIZE_MB` |

Production startup rejects debug/dev/test capabilities, weak or duplicate runtime
secrets, unsupported JWT algorithms, partial provider configuration, non-HTTPS
callbacks, non-Redis credential/auth limiter storage, disabled HTTPS, invalid proxy
networks, and non-HTTPS CORS origins. Provider secrets belong in the deployment secret
boundary and must never be compiled into Flutter.

## Optimizer

The default Compose mode sets `TWIN2CLOUDS_MODE=INFO`. Pricing contracts live in the
versioned `pricing_registry/` tree. Local file permission checks are disabled unless
the cloud overlay sets `ENABLE_LOCAL_CREDENTIAL_FILE_CHECKS=true`.

## Deployer

`DEPLOYER_RUNTIME_STATE_ROOT` points at a named-volume path. Runtime projects,
operation packages, and durable state must not use the versioned template directory.
Local credential-file checks use the same explicit overlay gate as the Optimizer.

## Flutter

Flutter uses compile-time Dart defines from JSON. See
[Runtime Profiles](../getting-started/runtime-profiles.md). Do not put cloud credentials
or Management API encryption/signing keys into Flutter configuration.
