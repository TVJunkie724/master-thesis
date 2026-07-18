# Troubleshooting

## `thesis.sh` Is Missing

Confirm you are at the repository root:

```bash
pwd
git rev-parse --show-toplevel
ls -l thesis.sh
```

The script is not inside `twin2multicloud_flutter` and should not be copied into a
worktree or subproject manually.

## Flutter Cannot Find `config/dev.json`

Generate it from the root:

```bash
./thesis.sh config
./thesis.sh flutter
```

When invoking Flutter manually, run from `twin2multicloud_flutter` and pass
`--dart-define-from-file=config/dev.json`.

## Docker Uses The Wrong Runtime

```bash
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh status
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh up --no-flutter
```

The project must not depend on containers from another repository with similar names.

## Management API Fails During Startup

Run `./thesis.sh secrets`. Common causes are missing, weak, equal, malformed, or known
placeholder JWT/encryption keys. If an existing DB contains encrypted CloudConnections,
restore its original encryption key; do not generate a replacement silently.

## Credential Validation Fails

Check connection purpose/provider/account metadata, validation message, permission-set
version, and whether the twin is bound to the intended deployment connection. Pricing
refresh uses a user-level pricing default, not an arbitrary twin.

Never paste the credential into logs or issue bodies. Re-bootstrap or replace a
connection through the application boundary.

## Pricing Is Stale Or Review-Required

Open Pricing Review from the dashboard, choose one provider, confirm the account, and
refresh. Inspect candidate/evidence details. Review-required means the contract refused
to publish an ambiguous/drifted result; it is not fixed by accepting a silent fallback.

## Deploy Is Disabled

Inspect configuration completion, CloudConnection validation, deployment preflight age,
artifact validation, and current twin state. A twin in `deploying`/`destroying` already
has an active operation; use status/history rather than starting another.

## An Azure Runtime Request Fails

Use the stable `error.code` to distinguish invalid input, authentication,
configuration, user-logic, upstream, and ADT-delivery failures. For 5xx/502 responses,
copy only `correlation_id` into log searches or issue evidence. Do not expect or request
raw exception text from the response; inspect the matching redacted runtime log.

An Event Checker batch may succeed while one action reports `EVENT_ACTION_FAILED`.
Use its `event_index` and `correlation_id`; the API intentionally does not echo the
configured event or downstream response.

## Tests Attempt Cloud Access

Stop and verify the command. Safe defaults exclude `tests/e2e`, do not enable the local
credential overlay, and do not call refresh/deploy/destroy/simulator cloud operations.
