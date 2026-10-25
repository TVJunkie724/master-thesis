---
title: "Restore managed Grafana for AWS and Azure"
description: "Bounded restoration of the original L5 service family, UI handoff and live evidence."
tags: [thesis, l5, grafana, evaluation]
lastUpdated: "2026-10-25"
version: "1.0"
---
<!-- SOURCES: user instruction 2026-10-25; FRONTEND_ARCHITECTURE.md;
integration_vision.md; existing provider layer_5_grafana.py modules;
docs/research/evaluation/l5-visualization-feasibility.md.
EXTRACTED: 2026-10-25 | VERSION: 1.0 -->

# Restore managed Grafana

## 0. Git branch

Continue `codex/phase-8-deployer-graph-resolver` in the primary checkout, from
`dc10353a`. Preserve unrelated untracked user documents. Focused intermediate
commits; no worktrees, history rewrite or push.

## 1. Summary and scope

The user explicitly requests planning, implementation and affected live E2E.
Every step below is required; a failed prerequisite is not a successful test.
Restore Amazon Managed Grafana and Azure Managed Grafana, not a self-hosted
replacement. Preserve L3 readers, L4 native services and Eventing ownership.
GCP L4/L5 remain excluded. The HTML/SVG observations remain historical evidence
for that implementation only; do not relabel them as Grafana passes.

In scope: one provider-local datasource and one existing Raw/Hourly dashboard
per workspace; existing operator sign-in; existing UI access card; cost and
graph corrections; bounded simulator evidence and cleanup. Out of scope:
redesign, embedded Grafana, alerts, HA, new human users/tenant consent, cross-cloud
L3-to-L5 authentication and repetition of unchanged Core permutations.

## 2. Visual layout (Desktop and Web unchanged)

```text
Twin lifecycle / Verify and access
+---------------- L4 ----------------+ +------------- L5 ----------------+
| Existing provider Twin surface     | | Amazon/Azure Managed Grafana    |
| Login identity / readiness         | | Login identity / readiness      |
| [Open] [Copy URL]                   | | [Open] [Copy URL]               |
+------------------------------------+ +---------------------------------+
```

Existing compact layout stacks these cards. Open navigates to the real
provider-owned dashboard, never to a Blob/file snapshot. No new screen.

## 3. Widget tree

```text
TwinOverviewScreen [MODIFY existing action dispatch]
  BlocBuilder<TwinOverviewBloc, TwinOverviewState> [REUSE]
    LayerAccessPanel [REUSE]
      LayerAccessCard [MODIFY snapshot explanation only]
        existing identity, readiness and details widgets [REUSE]
        _Actions / Open, Copy URL [REUSE]
```

## 4. Component specifications

Reuse `screens/twin_overview/twin_overview_screen.dart` and
`widgets/twin_overview/layer_access_panel.dart`. No constructor/parameter
changes or new widget. Dispatch snapshot fetch only for explicitly historical
snapshot capabilities; managed Grafana surfaces use the existing external
navigation handle. Auth mode comes from the typed Management read model:
`aws_identity_center` or `azure_entra`. No cloud secrets or Grafana automation
tokens enter Flutter. Historical snapshots remain distinguishable.

## 5. Responsive behavior

Retain existing 640-pixel compact boundary and all current layout constraints.
Below it, stacked cards/actions; above it, existing available-width layout.
Wide Desktop introduces no extra columns. Preserve high text scaling and Web.

## 6. State flow

```text
Management persisted deployment access -> existing BLoC -> access card
Open -> existing external launcher -> provider sign-in -> Grafana dashboard
```

The BLoC still owns loading, stale results, lifecycle and errors. Browser
sign-in is not marked verified by provisioning. No additional API or polling.

## 7. Design tokens

Reuse current AppSpacing, theme text/color tokens and Material icons. No new
tokens, dependencies or animation.

## 8. Interactions and states

Preserve disabled Open when not deployed/not ready, local launch-failure
feedback, Copy URL, loading/empty/error panels and cleanup guards. No URL
query credentials. Grafana login is intentionally separate from local app login.
Dashboard auto-refresh disabled; bounded raw and hourly time series only.

## 9. Accessibility

Retain existing keyboard traversal, button semantics, contrast and focus.
Accessible labels identify the provider surface; successful navigation is not
represented as a completed cloud/data assertion.

## 10. Cross-service implementation and live prerequisites

1. Reuse the existing Grafana Terraform/provider modules and dashboard builders.
   Remove the normal Six-layer SVG hosting resources; keep AWS_IAM reader URL
   authentication. The managed Infinity SDK credential-chain failure is live
   evidence. On 2026-10-25 the user explicitly approved a scoped alternative:
   Terraform owns one technical IAM user (no login profile) and its inline
   policy, permitting only this reader's IAM-authenticated Function URL.
   SDK postapply creates one access key in memory and stores it only through
   Grafana secureJsonData, never Terraform state/outputs, logs or Flutter.
   Retry replaces keys only on this tagged technical user; failed postapply
   revokes the new key. Terraform force_destroy removes SDK keys with the user.
   No administrator credentials, public reader, new human user or hosting change.
   Verify key lifecycle/failure paths and exact URL-only policy offline, then
   admit a fresh bounded live run only within the remaining authorized budget.
2. Azure Standard X1, managed identity, workspace-scoped deployer Admin and
   existing human Viewer. Reuse the bounded function-key datasource secret and
   existing JSON API dashboard. No new Entra users or warm Function instances.
3. Provision dashboard/datasource through existing SDK postapply hooks. Use one
   short-lived AWS provisioning service account per workspace; preserve its
   identity across bounded retries to avoid duplicate user licenses. Revoke
   tokens after use; workspace Destroy removes the service account. Azure uses
   existing Entra application authority. Record actual plugin/Grafana versions.
4. Update catalog bindings, provider service mapping and cost ownership together;
   regenerate contracts and immutable fixture digests. Reuse frozen Grafana
   rates where valid; don't price Grafana as a Lambda/Function renderer. Never
   mutate existing selected deployment evidence or the Five-layer baseline.
5. Keep existing Management access endpoint and schema, with accurate service,
   authentication, URL and capability metadata. Browser link includes fixed
   provisioned dashboard UID. Legacy snapshot evidence remains interpretable.
6. Before Apply: review exact plan, authenticated reader/plugin availability,
   operator identity, regional capacity, numerical reservation, timeout and
   independent cleanup inventory. Reserve license floors before creation;
   retries/new workspaces are not free. No trial/credit assumptions. Private
   spending authorization stays outside tracked documentation.

## 11. Required verification

Offline: Flutter analyze/test/Web/macOS baseline; scoped provider tests, real
Terraform validation/plan contract tests, catalog/price and access sync tests,
Management projection validation, Flutter link actions and full regression
suites. Integration uses the real local Management API, not mocked HTTP.

Minimum focused cases: AWS/Azure correct URL+auth (happy); missing output and
plugin/auth failure (unhappy); Core creates no L5, GCP excluded, wrong reader
provider rejected, historical SVG distinguished, Destroy disables access,
missing user rejected, immutable old result preserved, no secret URL/payload,
empty dashboard not accepted as data proof (edge). Reuse existing tests for
unchanged layout and lifecycle rather than duplicating them.

Live: one fresh representative normal deployment per provider, sequentially.
Record exact Terraform count and per-resource/operation timings. Use the real
downloaded simulator; assert correlated command, exact L3 raw/hourly and L4
projection. Assert Grafana datasource results match the same raw points and
hourly mean, then open via the UI and visually verify actual Grafana panels.
An API-only result or login page is not browser chart proof. If sign-in needs
the human operator, request it without leaking tokens or keeping resources
indefinitely. Functional deadline 45 minutes; trigger cleanup immediately on
failure/completion, with a separate 30-minute cleanup allowance and escalation
for residuals. Record any actual overrun; timers are not provider billing caps.
Do not repeat six unchanged directed Core tests without a regression reason.

## 12. Definition of done / review

- [x] Catalog/cost/runtime consistently identify managed Grafana, not SVG.
- [ ] AWS/Azure real dashboards provision automatically, no public L3 reader.
- [ ] Existing UI opens the correct dashboard with provider sign-in.
- [x] Relevant offline suites and Web/macOS builds pass.
- [ ] Each provider has exact simulator-data API and browser chart evidence.
- [ ] Destroy plus independent scoped zero inventory, including Grafana,
      permissions and provisioning identities, recorded for each live attempt.
- [ ] RQ1/RQ2/RQ3 claims and actual costs/limitations updated without rewriting
      historical passes; current docs no longer describe SVG as final L5.
- [ ] Intermediate commits created; remove this temporary plan after completion
      and migrate rationale to the decision log and status to execution plan.

Architect/builder review: existing surfaces/contracts reused, responsibilities
unchanged, no new product feature. Live execution is explicitly user-authorized,
but still conditional on exact resource/budget/prerequisite review. The user's
instruction to plan and implement supplies task approval; no extra design
approval loop is introduced. Offline baseline: 827 Flutter tests, analyze and
Web/macOS builds pass before changes.
