# Getting Started

There are two supported ways to experience the application:

| Mode | Docker | Cloud credentials | Purpose |
|---|---:|---:|---|
| Integrated development | required | not required | Flutter against all three local backend services. |
| Offline demo | not required | not required | Deterministic UI scenarios with in-memory adapters. |

The repository entrypoint is `./thesis.sh`. It owns local secret bootstrap,
Compose startup, Flutter runtime configuration, smoke checks, tests, documentation,
and the separate LaTeX command boundary.

## Fastest Safe Start

Offline UI:

```bash
./thesis.sh demo --setup
```

Full local application:

```bash
./thesis.sh up --setup
```

Neither command loads cloud credentials by default. The integrated stack can create
users, twins, configurations, pricing-review state, and mock deployment data without
contacting a provider.

Continue with [Fresh Clone](fresh-clone.md) or [Runtime Profiles](runtime-profiles.md).
