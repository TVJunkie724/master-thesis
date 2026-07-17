# Thesis Structure Review — Updated After Feedback

> **Historical planning note:** The research questions in this file have been
> superseded by
> [Research Questions And Evaluation Design](research/research_questions_and_evaluation_design.md).
> Do not transfer the RQ wording below into the thesis without reconciling it
> with that research source of truth.

## 1. Revised Research Questions

Centered on the thesis goal: *creating a fully functional deployed digital twin in the cloud from configurations alone,* while also considering the adaptation and integration of the two bachelor thesis prototypes.

| RQ | Question | Evaluated in |
|----|----------|-------------|
| **RQ1** | How can a configuration-driven platform be designed that transforms user-defined IoT scenario parameters into a fully functional, deployed digital twin across one or more cloud providers? | Ch 5 (Architecture), Ch 6 (E2E validation) |
| **RQ2** | How can independently developed, single-purpose prototypes (a cost optimizer and a cloud deployer) be refactored and integrated into a unified multi-cloud platform without discarding their core logic? | Ch 4 (Legacy Analysis + Refactoring) |
| **RQ3** | What deployment challenges and failure modes emerge when provisioning multi-cloud digital twin infrastructure, and how can they be systematically detected and resolved? | Ch 6 (E2E results, bugs found), Ch 7 (Discussion) |

> [!NOTE]
> These RQs cover the full thesis arc: **legacy integration (RQ2) → system design (RQ1) → validation & lessons learned (RQ3)**. Added to [introduction.tex](file:///Users/caroline/git/master-thesis/twin2multicloud-latex/chapters/introduction.tex) §1.3.

---

## 2. Chapter 4 Size — Recommendation

Keep Ch 4 as one chapter, but apply the **"methodology once, uniqueness per subsystem"** pattern:

| Section | Focus | Est. Pages |
|---------|-------|-----------|
| §4.1–4.3 (Legacy Analysis) | What existed, what was wrong, what was needed | 8–10 |
| §4.4 (Methodology) | Shared patterns: Protocol abstraction, component architecture, factory registration. Explain these *once* with one illustrative example | 3–4 |
| §4.5 (Optimizer) | What was *unique*: JS→Python rewrite, pricing API integration, formula extraction | 2–3 |
| §4.6 (Deployer) | What was *unique*: AWS-only→tri-cloud, imperative SDK→Terraform+SDK hybrid, gluecode layer | 3–4 |
| §4.7 (Management API + UI) | Built from scratch, so no "legacy → new" story — just the key decisions | 2–3 |
| **Total** | | **18–24** |

The key: §4.5–4.7 should each be 2–4 pages and *back-reference §4.4* instead of re-explaining the methodology.

---

## 3. Evaluation Planning

### What you have
- **11 E2E scenarios** (8 cross-cloud + 3 same-cloud), all passing
- **100% cross-cloud boundary coverage** (L1→L2, L2→L3, L3-Hot→L3-Cold, etc.)
- **19 test cases per scenario** covering deployment, data flow, event pipeline, and storage movers
- **15+ documented bug fixes** with root causes and resolutions
- **Deployment durations**: 6–48 min per scenario (but contain waits/sleeps, so ⚠️)

### What makes sense for evaluation

| Section | Content | Source |
|---------|---------|--------|
| §6.1 Experimental Setup | Cloud accounts, regions, test date, DT configuration used | E2E scenario configs |
| §6.2 E2E Test Framework | Test architecture (pytest, scenario configs, phases), what each test validates | [E2E_PROGRESS.md](file:///Users/caroline/git/master-thesis/3-cloud-deployer/tests/e2e/E2E_PROGRESS.md) |
| §6.3 Scenario Coverage | The provider configuration table (11 rows) + boundary coverage table | Already exists in E2E_PROGRESS.md |
| §6.4 Results | Pass/fail per scenario, skipped tests rationale, resource counts | E2E_PROGRESS.md summary table |
| §6.5 Bugs Discovered & Fixed | 5–8 most interesting bugs as "lessons learned" — each shows a cross-cloud edge case the tests caught | E2E_PROGRESS.md fixes section |
| §6.6 Threats to Validity | Single user, no concurrent deployments, pricing cache not live, GCP L4/L5 not implemented | Discussion cross-ref |

> [!IMPORTANT]
> **Deployment times: agree, not useful.** Times range 6–48 min and are dominated by cloud-side waits (Azure SCM startup: 2–5 min, Terraform provider downloads, GCP Firestore cooldown: 5 min). Reporting them as "performance metrics" would be misleading. Instead, mention them qualitatively: *"Deployment times ranged from 6 to 48 minutes, dominated by cloud-side resource initialization rather than platform logic."*

> **Cost accuracy: agree, not feasible.** You'd need to run IoT simulators at the exact message rate for a full billing cycle to validate. Instead, frame the cost model as *"the formulas are derived from published pricing APIs and validated against manual spot-checks of individual service costs, but end-to-end cost accuracy across a complete simulated IoT scenario was not evaluated."*

---

## 4. Related Work — Suggested Categories & Comments

Add these as `% TODO` comments in [relatedWork.tex](file:///Users/caroline/git/master-thesis/twin2multicloud-latex/chapters/relatedWork.tex):

```latex
% TODO: Add comparison table — rows = existing tools/papers, columns = features
% Features to compare:
%   - Multi-cloud support (AWS/Azure/GCP)
%   - Configuration-driven (no code required)
%   - IaC-based provisioning
%   - Cost estimation before deployment
%   - End-to-end data flow (ingestion → visualization)
%   - 5-layer architecture support
%   - Cross-cloud data transfer handling

% TODO: Categories to survey:
%   1. Digital Twin deployment platforms (Eclipse Ditto, Azure DT, AWS TwinMaker)
%   2. Multi-cloud IaC orchestration (Terraform, Pulumi, Crossplane)
%   3. Cloud cost prediction frameworks (Infracost, cloud pricing calculators)
%   4. IoT reference architectures (AWS IoT Greengrass, Azure IoT Reference Arch)
%   5. Multi-cloud management platforms (Anthos, Azure Arc)
%   Target: 10-15 papers/tools cited, with a comparison table
```

---

## 5. Discussion Ch 7 — Legacy vs. Unified Overlap

**Agreed.** Keep the comparison table in §7.2, but reduce the "8 architectural evolution patterns" bullets to single-sentence cross-references:

```
Instead of: "The Deployer evolved from imperative SDK calls to Terraform... [2 paragraphs]"
Write:      "Imperative→declarative (Section~\ref{sec:refactoring-deployer})"
```

---

## 6. Tech Stack Table — My Opinion

**Drop the version numbers.** Here's why:

- Version numbers are *maintenance debt* — they become wrong silently
- No supervisor or examiner will check that you used Python 3.11 vs 3.12
- What *matters* is the technology choice and its rationale (e.g., "FastAPI for async SSE support" or "SQLAlchemy for ORM-based schema management")

**Recommendation:** Keep the table but simplify columns to: **Component | Technology | Rationale**. Drop version numbers and the "38 `.tf` files" count. The table's value is showing *why* each technology was chosen, not cataloging exact versions.

---

## 7. IaC / Terraform Section — Separate Chapter?

**No, keep it in Ch 5.** The IaC section is part of the architecture, not a standalone topic. But it does deserve **more depth** — expand §5.5 from its current stubs to ~3–4 pages covering:

| Subsection | Content |
|-----------|---------|
| §5.5.1 File organization | How the `.tf` files are structured (by provider? by layer? shared vs. provider-specific?) |
| §5.5.2 The hybrid model | What Terraform handles vs. what SDK post-apply handles (and *why*) — this is partially in §5.3 already, consolidate here |
| §5.5.3 Variable generation | The `tfvars_generator` pipeline — already written at line 344, just needs a section header |
| §5.5.4 Representative snippet | One well-chosen `.tf` example showing the abstraction pattern |

This shouldn't make Ch 5 much longer — you're mostly reorganizing existing prose under clearer headings.

---

## 8. Data Flow & Layer Architecture Diagram

### What exists

You have **excellent source material** in the deployer docs:
- [docs-architecture.html](file:///Users/caroline/git/master-thesis/3-cloud-deployer/docs/docs-architecture.html): 5-layer breakdown with per-layer cloud services + high-level data flow ASCII diagram
- [docs-multi-cloud.html](file:///Users/caroline/git/master-thesis/3-cloud-deployer/docs/docs-multi-cloud.html): Universal gluecode pattern, multi-cloud decision tree, L3 mover flow, L3→L4 data access flow
- E2E_PROGRESS.md: Event flow architecture (Dispatcher → Processor → Persister → Hot Storage → Event-Checker)

### What the thesis needs

A single **end-to-end data flow diagram** that shows:

1. IoT Device → L1 (Dispatcher) → L2 (Processor → Persister) → L3 (Hot → Cold → Archive) → L4 (Twin) → L5 (Grafana)
2. Where cross-cloud gluecode functions are injected (Connector, Ingestion, Writer)
3. The event processing side path (Event-Checker → Workflow → Feedback)

**Proposed placement:** New §5.6 "End-to-End Data Flow" between the current Deployer section and the Flutter UI section. Content:
- The diagram (generated as a LaTeX figure)
- 1–2 paragraphs narrating the flow
- The "universal gluecode pattern" explanation (from `docs-multi-cloud.html`)
- A table of cross-cloud boundary handling (already exists in the deployer docs)
- Brief mention of error handling strategy (what happens when a gluecode POST fails: retry with exponential backoff, max 3 attempts, then log error)

---

## 9. ZIP Assembly — Already Described ✅

Yes, this is already well-covered in Ch 5. Specifically:
- [Line 258](file:///Users/caroline/git/master-thesis/twin2multicloud-latex/chapters/systemArchitecture.tex#L258): Describes the project ZIP contents in detail
- [Line 443](file:///Users/caroline/git/master-thesis/twin2multicloud-latex/chapters/systemArchitecture.tex#L443): The deployment trigger flow (assemblies ZIP from DB records)
- [Line 460](file:///Users/caroline/git/master-thesis/twin2multicloud-latex/chapters/systemArchitecture.tex#L460): The `build_project_zip` function description

No additional work needed here.

---

## 10. State Synchronization — Already Described ✅

Also already covered in §5.7 "Data Flow and State Management" (lines 449–462):
- Brain: stateless (line 454)
- Muscle: file-based, Terraform state (line 456)
- Management API: database-backed, 7 tables (line 458)
- How the API bridges both (line 460)

This section could use a **diagram** (a simple box-and-arrow showing which service owns which state), but the prose is complete.

---

## 11. Error Handling — Placement Plan

**Agreed: add near the data flow description.** Specifically, after the proposed §5.6 "End-to-End Data Flow," add a subsection:

### §5.6.x Error Handling Strategy

| Failure Point | What Happens | Recovery |
|--------------|-------------|----------|
| Terraform `apply` fails mid-step | Twin → `ERROR` state, partial resources remain | User can retry or destroy |
| Provider API timeout during SDK post-deploy | Retry with backoff (15 retries × 30s for Kudu) | Falls back to error state after exhaustion |
| Cross-cloud gluecode POST fails | Retry with exponential backoff (3 attempts) | Log error; data may be lost for that message |
| Credentials expire mid-deployment | Terraform fails with auth error | Twin → `ERROR`; user must update credentials and retry |
| Deployer crashes mid-operation | Session reaper detects stuck twin after 30 min | Automatically recovers twin state from `DEPLOYING` → `ERROR` |

This is a 0.5–1 page addition that addresses the domain expert concern without needing a separate chapter.

---

## Priority Actions (Updated)

| # | Action | Status |
|---|--------|--------|
| P0 | Add RQs to Introduction §1.3 | TODO — use table above |
| P1 | Add `% TODO` comments to `relatedWork.tex` | TODO |
| P2 | Write Ch 4 §4.4–4.7 (refactoring sections) | In progress — drafts exist |
| P3 | Write Ch 6 Evaluation based on E2E results | TODO |
| P4 | Expand Ch 5 §5.5 (IaC) with file structure and hybrid model | TODO |
| P5 | Create end-to-end data flow diagram + §5.6 prose | TODO |
| P6 | Simplify tech stack table (drop versions, add rationale) | TODO |
| P7 | Reduce Ch 7 overlap (single-sentence back-refs) | TODO |
