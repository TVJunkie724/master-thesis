# Project Setup

Use the [Fresh Clone](../getting-started/fresh-clone.md) path first. Developer variants:

```bash
./thesis.sh setup
./thesis.sh up --no-flutter --build
./thesis.sh flutter
./thesis.sh docs up
```

Raw service commands are useful only for debugging. Compose bind-mounts all Python
projects, so source changes are visible in containers; dependency changes require image
rebuilds. Flutter runs on the host.

The entrypoint detects macOS, Windows, or Linux unless `--device` is supplied.
Windows execution uses Git Bash. Native prerequisites and build guarantees are
defined under [Supported Platforms](../getting-started/supported-platforms.md).

## Local Files

Do not commit:

- `.secrets/runtime/*`;
- `.secrets/local/*`;
- generated `twin2multicloud_flutter/config/dev.json`;
- Management API database/uploads;
- runtime deployment state;
- provider-generated credentials or Terraform state.

Never delete existing credential material merely because a new setup path exists.
Migrate/revoke it deliberately after validation.

## Service APIs

With the stack running:

- Management API: `http://localhost:5005/docs`;
- Optimizer: `http://localhost:5003/docs`;
- Deployer: `http://localhost:5004/docs`.

The OpenAPI documents are exact endpoint references; this site explains architecture
and workflow semantics.
