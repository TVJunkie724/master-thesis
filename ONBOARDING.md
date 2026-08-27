# Twin2MultiCloud Repository Onboarding

Status: current contributor entrypoint

## Read first

1. `docs/plans/2026-08-26_thesis_poc_target_concept.md`
2. `docs/research/research_questions_and_evaluation_design.md`
3. `docs/plans/2026-08-26_thesis_poc_execution_plan.md`
4. `docs/plans/2026-08-26_poc_credentials.md`
5. `docs/development_and_decision_log.md`

Read the component README and relevant shared contract before changing a
service. Current code/contracts/tests override superseded prose; Git history is
the archive for removed plans and handoffs.

## Repository map

| Path | Responsibility |
|---|---|
| `twin2multicloud_flutter/` | Management-only Flutter client and offline demo |
| `twin2multicloud_backend/` | application state, orchestration and public API |
| `2-twin2clouds/` | frozen pricing, cost calculation and graph resolution |
| `3-cloud-deployer/` | readiness, provider execution, verification and cleanup |
| `contracts/` | canonical shared wire contracts |
| `docs-site/` | current user/developer handbook |
| `docs/research/` | research method and evidence |
| `twin2multicloud-latex/` | thesis source |

## Non-negotiable boundaries

- only `six-layer-eventing@1` is deployable;
- Five-layer v1 is Optimizer-only offline baseline evidence;
- cost is the only scoring objective;
- pricing inputs are frozen cited/hashed snapshots;
- Flutter calls only Management;
- deployment credentials flow only Management -> Deployer for a current
  request;
- deployed Twin definitions are immutable;
- provider mutations require an exact plan and explicit confirmation;
- ordinary tests and documentation builds perform no provider mutation;
- mocks/fixtures are never described as live evidence.

## Credential safety

Never print, commit, copy into issues, or place credentials in test output.
Supported CloudConnection imports are write-only AWS CSV, Azure JSON and GCP
JSON. Responses contain only non-secret identity/scope metadata.

Do not run Terraform Apply/Destroy, provider CLIs, pricing fetches, browser
login automation, or live E2E without explicit supervised authorization.

## Git workflow

- inspect `git status` before editing;
- preserve unrelated user changes;
- use `codex/` for new agent branches unless a different branch is requested;
- create dependency-ordered commits with focused messages;
- do not rewrite or destructively reset user history;
- never push unless the user asks;
- record AI-assisted commits using the repository trace prefix when required.

## Safe verification

From the repository root, prefer the scoped `thesis.sh` gates. Service-local
fallbacks are:

```bash
cd 2-twin2clouds && PYTHONPATH=. python -m pytest -q
cd twin2multicloud_backend && APP_ENV=test PYTHONPATH=. python -m pytest -q
cd 3-cloud-deployer && PYTHONPATH=. python -m pytest -q
cd twin2multicloud_flutter && flutter analyze && flutter test
```

Also run shared contract sync/check scripts, Terraform validation, OpenAPI
snapshot generation, secret/static checks and MkDocs strict build when those
areas change.

## Evidence discipline

Every retained capability maps to a research question, mutation-safety need or
reproducibility need. New breadth requires an explicit scope decision.

The final live target is nine supervised Small scenarios: three provider-local
and six directed AWS/Azure/GCP pairs selected by a coverage matrix. Stop on the
first unresolved prerequisite rather than leaving a full environment running.

Important design rationale belongs in
`docs/development_and_decision_log.md`; active execution status belongs in the
single thesis PoC execution plan. Do not create new product roadmaps,
implementation handoffs or distributed TODO/future-work promises.
