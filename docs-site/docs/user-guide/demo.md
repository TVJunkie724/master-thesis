# Offline Demo

```bash
./thesis.sh demo --setup
```

The demo starts Flutter only. It uses in-memory implementations of the same API/log
interfaces as the integrated app and displays a persistent demo banner.

| Scenario | Purpose |
|---|---|
| `showcase` | populated twins, pricing, configuration, operations, and review states |
| `empty` | first-use and empty-state UX |
| `degraded` | stale/review-required pricing and recoverable failure states |

The demo permits screen walkthroughs and deterministic interactions but does not prove:

- backend migration/startup;
- provider credentials or permissions;
- current cloud catalog responses;
- Terraform deployment correctness;
- institutional authentication.

Any feature added to the user-visible Management API should receive corresponding demo
adapter behavior and fixture/test coverage so every screen remains inspectable.
