# Runtime modes

Flutter fails closed when `APP_MODE` is absent or invalid.

| Mode | API adapter | Identity | Use |
|---|---|---|---|
| `development` | network Management API | explicit configured local bearer | integrated local PoC and supervised evaluation |
| `demo` | in-memory demo adapter | fixture user | offline walkthrough and deterministic UI tests |

`./thesis.sh config` writes ignored `config/dev.json` with the local API URL and
development token. `config/demo.json` is tracked and contains no network URL or
credential.

The repository may retain fail-closed build scaffolding for other environments,
but production authentication and public deployment are not supported thesis
capabilities.
