# Getting Started

Two safe modes are supported:

| Mode | Docker | Cloud credentials | Purpose |
|---|---:|---:|---|
| Integrated development | required | not required | Flutter against the three local Python services |
| Offline demo | not required | not required | deterministic UI behavior through in-memory adapters |

The root entrypoint is `./thesis.sh`.

## Fastest safe start

Offline UI:

```bash
./thesis.sh demo --setup
```

Integrated local application:

```bash
./thesis.sh up --setup
```

These commands do not contact a cloud provider and do not read deployment
credentials. They can create local users, Twins, configurations, calculations,
readiness fixtures, and deployment-operation fixtures only.

Continue with [Fresh Clone](fresh-clone.md) or
[Runtime Profiles](runtime-profiles.md). Provider mutations belong only to the
separately supervised evaluation workflow.
