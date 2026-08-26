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

Check connection purpose/provider/account metadata, validation message, and
whether the twin is bound to the intended deployment connection. Pricing
refresh uses a user-level pricing default, not an arbitrary twin.

Never paste the credential into logs or issue bodies. Replace the
CloudConnection through the write-only application boundary and revoke the old
credential directly with the provider.

## Pricing Is Stale Or Review-Required

Open Pricing Review from the dashboard, choose one provider, confirm the account, and
refresh. Inspect candidate/evidence details. Review-required means the contract refused
to publish an ambiguous/drifted result; it is not fixed by accepting a silent fallback.

## Deploy Is Disabled

Inspect configuration completion, CloudConnection validation, deployment preflight age,
artifact validation, and current twin state. A twin in `deploying`/`destroying` already
has an active operation; use status/history rather than starting another.

## Manifest Or Deployment Graph Preflight Fails

Operation packages require Manifest v4 owned by the frozen Six-layer profile.
Historical Five-layer calculations are not deployable. Do not downgrade the archive or copy values from `cheapest_l*`
fields. Use the stable code to locate the owning contract:

| Code family | Check |
|---|---|
| `DEPLOYMENT_MANIFEST_*` | Six-layer v4 schema, bounded inventory, secret-free manifest |
| `DEPLOYMENT_ARCHITECTURE_*` | selected run, architecture/specification cross-links and digests |
| `DEPLOYMENT_PROFILE_CATALOG_MISMATCH` | exact generated profile/catalog copies and digests |
| `DEPLOYMENT_GRAPH_NODE_*`, `EDGE_*`, `BINDING_*`, `CYCLE_*` | registered component, edge, port, trust, and binding ownership |
| `DEPLOYMENT_PACKAGE_CATALOG_MISMATCH` | selected artifact source/builder and deterministic package evidence |
| `DEPLOYMENT_TERRAFORM_BINDING_INVALID` | catalog variable/resource/output symbol and value type |
| `DEPLOYMENT_GRAPH_RESUME_MISMATCH` | retry/destroy differs from the successful operation's frozen evidence |

Run the safe gate from the repository root:

```bash
./thesis.sh test deployment-contract --focused
```

Errors expose bounded IDs and a correlation ID. Do not add physical resource names,
tfvars, credentials, provider responses, or source code to an issue.

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

## Phase 8 Evaluation Drift

Run the frozen local checks from the repository root:

```bash
docker --context orbstack compose run --rm --no-deps \
  -v "$PWD:/workspace" -w /workspace 2twin2clouds \
  python scripts/phase_08_profile_evaluation/validate.py
```

A digest error means a pinned contract, workload, implementation, pricing,
source, generator, schema, or result changed. Do not patch generated JSON by
hand. Reconcile the source and rerun `generate.py`, then require the
byte-identical `verify_reproducibility.py` gate. Neither command requires or
uses provider credentials.
