# Aktuelle Architektur-Schulden und Refactoring-Roadmap

**Datum:** 2026-04-26
**Scope:** `2-twin2clouds` (Brain), `3-cloud-deployer` (Muscle), `twin2multicloud_backend` + `twin2multicloud_flutter` (Orchestrator)
**Ziel:** Alle gravierenden Architektur-Schulden benennen, nach Risiko priorisieren und eine Roadmap definieren, um sie schrittweise aufzulösen.

Dieses Dokument beschreibt nur den **aktuellen Befund**. Bereits erledigte Altlasten wie `2-twin2clouds/backend/deprecated_calculation/`, doppelte Backend-Entry-Points im Management API und archivierte alte Implementation Plans sind hier nicht mehr als offene Findings enthalten.

---

## 0. Kurzurteil

Das System ist ein funktionierender Research-Prototyp mit einem tragfähigen Kern: Optimizer, Deployer, Management API und Flutter UI greifen grundsätzlich ineinander. Die größten Risiken liegen nicht mehr in fehlenden Dateien oder totem Code, sondern in **uneindeutigen Architektur-Grenzen**, **zu großen Verantwortlichkeits-Clustern**, **nicht gekapselten Integrationspunkten** und **unklarer Credential-/Runtime-Ownership**.

Die erste Schuld, die gelöst werden sollte, ist technisch umgesetzt und Docker-verifiziert:

> **P0: Deployer-Dual-Hierarchie auflösen (`3-cloud-deployer/src/aws/` vs. `3-cloud-deployer/src/providers/aws/`).**

Diese Schuld blockierte fast alle anderen sauberen Refactorings im Deployer. Die Phase-1-Implementierung konsolidiert den produktiven Pfad auf `src/providers/*` + `TerraformDeployerStrategy` und ist Docker-verifiziert.

Der nächste priorisierte Architekturblock ist:

> **P0: Repository Hygiene & Documentation Architecture.**

Dieser Block trennt aktive Produktdateien von historischen Artefakten, klaert die Ownership von `upload/template` als Deployment-Vorlage und fuehrt eine wartbare MkDocs-basierte Dokumentationsseite ein. Direkt danach folgt Runtime, Credentials & Deployment State Hardening: Dev-/Demo-/Cloud-Runtime trennen, Cloud Connections zur user-scoped Credential Source of Truth machen, Admin-Credentials aus Persistenz entfernen und Flutter User Intent von Deployer-/Terraform-Dateistrukturen entkoppeln.

---

## 1. Aktueller Befund nach Projekt

| Projekt | Aktueller Architekturzustand | Größtes Risiko |
|---------|------------------------------|----------------|
| `2-twin2clouds` | Funktionsfähiger Optimizer mit guter Price-Fetcher-Factory, aber duplizierter Layer-Logik und vielen Raw-Dicts. | Provider-/Layer-Kalkulation ist schwer erweiterbar und fehleranfällig. |
| `3-cloud-deployer` | Phase-1-Konsolidierung auf `src/providers/*` + `TerraformDeployerStrategy` ist umgesetzt und Docker-verifiziert; globale Projektzustände, statische Credential-Dateipfade, unklare Template-/Upload-Ownership und sehr große API-/Validation-Module bleiben. | Expliziter Deployment Context, klare Template-/Runtime-Trennung, isolierte Deployment Workspaces und kleinere API-/Validation-Module. |
| `twin2multicloud_backend` | Management API ist der richtige Orchestrator, aber `twins.py` bündelt CRUD, State Machine, Upload, Deployment, SSE und Test-Flows; Credential- und Deployment-State-Ownership sind noch nicht sauber getrennt. | Business-Logik steckt in Routes statt in Services/Domain; Credentials brauchen eine CloudConnection-Domain. |
| `twin2multicloud_flutter` | UI nutzt Riverpod, BLoC, Dio und `go_router`; funktional, aber mit großen Smart Widgets/BLoCs und hardcoded Dev-Auth. | Wizard- und Twin-Views sind schwer testbar; Credential-Auswahl und Twin-Konfiguration muessen als User Intent statt Deployer-Config modelliert werden. |

---

## 2. Offene Architektur-Schulden

### P0-1: Deployer-Dual-Hierarchie

**Befund:**
Die Phase-1-Implementierung konsolidiert den Deployer auf einen produktiven Pfad:

- `3-cloud-deployer/src/providers/deployer.py` als canonical deploy/destroy facade
- `3-cloud-deployer/src/providers/terraform/TerraformDeployerStrategy` als einzige IaC-Ausführungsschicht
- `3-cloud-deployer/src/providers/{aws,azure,gcp}/` als Provider-Implementierungen
- `3-cloud-deployer/src/main.py` als dünner CLI-Adapter auf den canonical path

Aktuelle Evidenz:

- `3-cloud-deployer/src/aws/`, `src/deployers/*` und `src/info.py` wurden aus dem produktiven Source Tree entfernt.
- `tests/unit/core_tests/test_architecture_boundaries.py` verhindert neue produktive Imports von `aws.*` oder `src.aws.*`.
- `tests/api/test_deployment_routes.py` prüft mit harten Assertions, dass Deploy, Destroy und Streaming über die canonical facade laufen.
- `TODOS.md` enthält keinen aktiven `!!3-cloud-deployer`-Migrationspunkt mehr.

**Warum gravierend:**
Diese Schuld war gravierend, weil es keinen eindeutigen canonical path für Deployment gab. Neue Arbeit konnte versehentlich die Legacy-Schicht stabilisieren statt die Zielarchitektur.

**Zielbild:**
`src/providers/*` + `TerraformDeployerStrategy` sind der einzige produktive Deployment-Pfad. Dieses Zielbild ist implementiert und per Docker-Testlauf verifiziert; der Audit-Review bleibt als formales Gate offen.

---

### P0-2: Repository Hygiene, Template Ownership und Dokumentationsarchitektur

**Befund:**
Aktive Produktdateien, historische Artefakte, Runtime-Uploads, Templates und Dokumentation sind noch nicht sauber getrennt:

- `3-cloud-deployer/upload/template` ist fachlich eine wertvolle Deployment-Vorlage, wurde aber zugleich als Development- und Runtime-Ort benutzt.
- `upload/` vermischt damit Template-Ownership und generierte Projektartefakte.
- Die aktuelle Deployer-Dokumentation ist teilweise als lose HTML-Dokumentation im Service gewachsen.
- READMEs tragen zu viel operative Detaildokumentation und bleiben dadurch schwer als canonical Einstiegspunkt aktuell zu halten.
- Historische Implementation Plans und Dokumente sind nicht ueberall klar als aktiv, archiviert oder obsolete klassifiziert.

**Warum gravierend:**
Bevor Credentials, Compose-Profile und Deployment Workspaces sauber getrennt werden koennen, muss klar sein, welche Dateien aktiv, historisch, Template, Runtime oder Dokumentation sind. Sonst wandern alte Pfade und Begriffe in die neue Architektur weiter. Besonders `upload/template` darf nicht geloescht werden; es braucht eine explizite Rolle als versionierte Deployment-Vorlage.

**Zielbild:**
Das Repository trennt aktive Produktpfade, versionierte Templates, Runtime-Artefakte und Dokumentation. `upload/template` wird entweder nach `3-cloud-deployer/templates/deployment_project` migriert oder kurzfristig explizit als Template abgesichert. Die Dokumentation wandert in eine MkDocs-basierte Docs-Site mit Docker-Dev-Server und Auto-Reload. READMEs bleiben kurze Einstiegspunkte.

**Konzept:** [`docs/plans/2026-04-26_repository_hygiene_documentation_architecture.md`](docs/plans/2026-04-26_repository_hygiene_documentation_architecture.md)

**Cleanup Plan:** [`docs/plans/2026-04-26_repository_hygiene_cleanup_plan.md`](docs/plans/2026-04-26_repository_hygiene_cleanup_plan.md)

---

### P0-3: Runtime, Credentials und Deployment State ohne klare Source of Truth

**Befund:**
Die lokale Runtime, Cloud-Credentials und generierte Deployment-Artefakte sind noch nicht sauber getrennt:

- `compose.yaml` mountet Credential-Dateien aus dem Repo-Root in mehrere Container.
- `README.md` dokumentiert aktuell parallele GCP-Dateien fuer verschiedene Services.
- Der Management API Seed-Pfad liest Credentials aus gemounteten Dateien.
- Der Backend-Deployment-Service schreibt `config_credentials.json` und `gcp_credentials.json` in Deployment-ZIPs.
- Der Deployer hat historisch Template- und Projektordner als Credential-/Config-Transport genutzt.
- Flutter modelliert Credential- und Deployer-Konfiguration noch zu nah am Deployment-Dateiformat.

**Warum gravierend:**
Credentials sind ein systemweiter Architekturvertrag, kein lokales Dateidetail. Solange Repo-Dateien, Docker-Mounts, Upload-Templates, DB-Felder und Deployer-Workspaces alle potenziell Credential-Quellen sind, gibt es keine klare Security Boundary. Das blockiert Least Privilege, sichere Bootstrap-Flows, saubere DB-Migrationen und eine verstaendliche Flutter-Konfiguration.

**Zielbild:**
Die Management API verwaltet user-scoped `CloudConnection`-Ressourcen als einzige fachliche Credential Source of Truth. Admin-Credentials werden nur fuer Bootstrap verwendet und nie persistiert. Twins referenzieren Cloud Connections. Flutter sendet User Intent. Der Deployer erhaelt pro Deployment ein canonical `DeploymentManifest` plus Runtime Credential Context und materialisiert nur ephemere, isolierte Deployment Workspaces.

**Konzept:** [`docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md`](docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md)

---

### P0-4: Backend God-Route und fehlende Service-/Domain-Schicht

**Befund:**
`twin2multicloud_backend/src/api/routes/twins.py` hat 1 725 LOC und bündelt:

- Twin CRUD
- State-Transition-Validierung
- Optimizer- und Deployer-Orchestrierung
- Upload-/ZIP-Handling
- Deployment-Logs und SSE-Nähe
- Test-Deploy/Test-Destroy-Flows
- direkte SQLAlchemy-Queries
- direkte `httpx.AsyncClient`-Calls

Aktuelle Evidenz:

- Viele `db.query(DigitalTwin)...`-Zugriffe liegen direkt in Route-Handlern.
- Mehrere `httpx.AsyncClient(...)`-Calls liegen direkt in Routes.
- `ENABLE_TEST_ENDPOINTS=true` ist in `compose.yaml` aktuell aktiv.
- Test-Endpunkte `/{twin_id}/test-deploy` und `/{twin_id}/test-destroy` liegen in `twins.py`.

**Warum gravierend:**
Die Management API ist der zentrale Orchestrator. Wenn Orchestrierung, Datenzugriff, State Machine und HTTP-Integration in einer Route-Datei stecken, sind Fehler schwer isolierbar. Außerdem wird jede Änderung am Deployment-Lifecycle riskant.

**Zielbild:**
Routes sind dünne HTTP-Adapter. Domain-/Service-Schichten übernehmen:

- `TwinRepository`
- `TwinLifecycleService`
- `DeploymentOrchestrator`
- `OptimizerClient`
- `DeployerClient`
- `DeploymentLogService`

---

### P0-5: Globale Projektzustände im Deployer

**Befund:**
Der Deployer nutzt `src/core/state.py` als globalen Active-Project-Zustand. Mehrere API-Module und Tests lesen `state.get_active_project()`.

**Warum gravierend:**
Globale Zustände sind gefährlich für parallele Requests, mehrere Nutzer, mehrere Twins und Test-Isolation. Für einen lokalen Demo-Flow kann das funktionieren; für eine robuste Orchestrierung ist es eine strukturelle Schwäche.

**Zielbild:**
Der aktive Projekt-/Twin-Kontext wird explizit pro Request bzw. pro Deployment-Kontext übergeben. `DeploymentContext` wird zur zentralen, immutable Datenstruktur für Deployer-Flows.

---

### P1-1: Flutter God-BLoC und God-Widgets

**Befund:**
Mehrere UI-Dateien sind deutlich zu groß:

| Datei | LOC |
|-------|-----|
| `twin2multicloud_flutter/lib/bloc/wizard/wizard_bloc.dart` | 1 912 |
| `twin2multicloud_flutter/lib/screens/twin_overview/twin_overview_screen.dart` | 1 425 |
| `twin2multicloud_flutter/lib/screens/wizard/step3_deployer.dart` | 1 265 |
| `twin2multicloud_flutter/lib/widgets/calc_form/calc_form.dart` | 1 197 |

Zusätzlich mischt das Frontend Riverpod und BLoC. Das ist nicht automatisch falsch, aber ohne klare Ownership-Regeln wird es schwer wartbar.

**Warum gravierend:**
Der Wizard ist fachlich zentral. Wenn Navigation, Validierung, Persistenz, Optimizer-Resultate, Deployer-Dateien und UI-Feedback in einem BLoC hängen, werden Tests und Änderungen teuer.

**Zielbild:**
Feature-Slices mit klarer Ownership:

- Wizard Shell / Navigation
- Step 1: Twin + Credentials
- Step 2: Optimizer
- Step 3: Deployer Config
- Deployment/Twin Detail getrennt vom Dashboard

State-Management-Regel: Riverpod für App-/Service-Provider, BLoC für explizite Feature-State-Machines. Keine stillen Überschneidungen.

---

### P1-2: Brain Layer-Calculation mit gemeinsamem Contract (behoben)

**Aktueller Stand:**
AWS, Azure und GCP verwenden genau ein validiertes, immutable `LayerResult` sowie
den gemeinsamen `LayerCalculatorSet`-Contract und die
`BaseLayerCalculatorSet`-Invarianten. Provider-spezifische Formeln bleiben
gekapselt, während Capability-Abfrage, Result-Erzeugung und Optimizer-Selektion
einheitlich sind.

Unsupported Provider-Layer werden mit Begründung modelliert und anhand ihres
canonical `supported`-Status aus der Scoring-Auswahl entfernt. Eine gemeinsame
Testmatrix prüft alle 21 Provider-Layer-Kombinationen. Damit kann ein nicht
implementierter Zero-Cost-Pfad nicht als vermeintlich günstigste Option gewinnen.

**Nachweis:**
[#68 Standardize optimizer LayerResult and layer calculator contracts](https://github.com/TVJunkie724/master-thesis/issues/68)
und `2-twin2clouds/implementation_plans/2026-07-17_layer_result_calculator_contracts.md`.

---

### P1-3: Untypisierte Integrationsgrenzen

**Befund:**
Zwischen Flutter, Management API, Optimizer und Deployer laufen viele Daten als `Map<String, dynamic>`, `Dict[str, Any]` oder rohe JSON-Dicts. Backend-Routes bauen HTTP-Requests zu Optimizer/Deployer direkt.

**Warum gravierend:**
Schema-Drift wird spät entdeckt. Feldnamen, Provider-Namen (`gcp` vs `google`) und State-Transitions können an mehreren Stellen auseinanderlaufen.

**Zielbild:**
Explizite DTOs pro Grenze:

- Flutter models für API Responses
- Pydantic Request/Response-Modelle in Management API
- typed clients `OptimizerClient` und `DeployerClient`
- contract tests für kritische Endpunkte

---

### P1-4: Fehlerbehandlung, Retry und Observability inkonsistent

**Befund:**
Der Deployer enthält viele breite `except Exception`-Blöcke. Eine aktuelle Suche findet 520 Treffer in `3-cloud-deployer/src` und `tests`. Backend-HTTP-Calls zu Optimizer/Deployer haben keine zentrale Retry-/Circuit-Breaker-Strategie.

**Warum gravierend:**
Cloud- und Terraform-Flows sind grundsätzlich fehleranfällig. Ohne einheitliche Fehler-Taxonomie und Retry-Policy ist schwer erkennbar, ob ein Fehler transient, validierungsbedingt, credential-bedingt oder ein Systemdefekt ist.

**Zielbild:**
Gemeinsame Fehler-Taxonomie:

- `ValidationError`
- `CredentialError`
- `CloudProviderError`
- `TerraformError`
- `TransientIntegrationError`
- `DeploymentStateError`

Dazu strukturierte Logs, Correlation IDs und zentrale Retry-Policies an Integrationsgrenzen.

---

### P2-1: Dev-/Test-Konfiguration ist zu nah am Default-Pfad

**Befund:**
Dieser Punkt ist ein Teilaspekt von P0-3 und bleibt hier nur als sichtbare UI-/Runtime-Symptomatik stehen.

`compose.yaml` setzt aktuell:

- `JWT_SECRET_KEY=${JWT_SECRET_KEY:-dev-secret-key}`
- `DEBUG=true`
- `ENABLE_TEST_ENDPOINTS=true`

Flutter enthält `dev-token` in `api_config.dart` und `api_service.dart`.

**Warum relevant:**
Für lokale Entwicklung ist das bequem. Für Architektur-Klarheit muss aber eindeutig sein, was Demo-/Dev-Verhalten ist und was Produktionsverhalten wäre.

**Zielbild:**
Getrennte Compose-/Env-Profile:

- `compose.dev.yaml`
- `compose.demo.yaml`
- `compose.cloud.yaml`

Dev-Auth und Test-Deploys werden explizit eingeschaltet, nie implizit.

---

### P2-2: Flutter-Dokumentationslinks umgehen die Management-API-Kapselung

**Befund:**
`twin2multicloud_flutter/lib/config/docs_config.dart` enthält direkte Links auf:

- `http://localhost:5003/documentation/`
- `http://localhost:5004/documentation/`

Das sind aktuell nur Dokumentationslinks, keine API-Calls.

**Warum relevant:**
Formal exponiert die UI interne Service-URLs. Das verletzt die Architekturregel weniger stark als direkte API-Calls, zeigt aber, dass die Kapselung nicht vollständig durchgezogen ist.

**Zielbild:**
Docs werden entweder über die Management API verlinkt/proxied oder als statische Projekt-Dokumentation in der UI gebündelt.

---

## 3. Roadmap zur Schuldenauflösung

### Phase 0: Assessment bereinigen und Debt-Backlog einfrieren

**Ziel:** Dieses Dokument ist die aktuelle Quelle der Wahrheit.

**Deliverables:**

- Historische Findings aus `ASSESSMENT.md` entfernen.
- Offene Schulden als P0/P1/P2 klassifizieren.
- Jede Schuld bekommt Evidenz, Zielbild und Exit-Kriterien.
- Danach keine parallelen TODO-Listen mehr als Architektur-Quelle verwenden; `TODOS.md` wird entweder bereinigt oder auf diese Roadmap verlinkt.

**Exit-Kriterien:**

- `ASSESSMENT.md` enthält keine erledigten Altfunde mehr.
- Die erste technische Phase ist eindeutig benannt: Deployer-Dual-Hierarchie.

---

### Phase 1: Deployer Architecture Canonicalization

**Ziel:** Ein einziger produktiver Deployer-Pfad.

**Implementation Plan:** [`3-cloud-deployer/implementation_plans/2026-04-24_14-40_deployer_architecture_canonicalization.md`](3-cloud-deployer/implementation_plans/2026-04-24_14-40_deployer_architecture_canonicalization.md)

**Reihenfolge:**

1. Import-/Call-Graph dokumentieren: Legacy `src/aws/*` vs. `src/providers/*`.
2. Entscheiden und dokumentieren: canonical path ist `src/providers/*` + `TerraformDeployerStrategy`.
3. Legacy-Pfade klassifizieren:
   - delete
   - migrate
   - temporary compatibility wrapper
4. Tests in Gruppen teilen:
   - canonical provider tests
   - terraform strategy tests
   - legacy tests to migrate/delete
5. `src/main.py`, `src/deployers/*`, `src/info.py` vom Legacy-Import lösen.
6. `!!3-cloud-deployer/` entweder entfernen oder als externes Archiv dokumentieren, nicht als aktive Quelle.

**Exit-Kriterien:**

- Kein produktiver Code importiert mehr `aws.*` aus `3-cloud-deployer/src/aws`.
- AWS läuft über denselben Provider-/Terraform-Pfad wie Azure/GCP.
- Tests beschreiben nur noch den canonical path.
- `TODOS.md` enthält keinen aktiven `!!3-cloud-deployer`-Migrationspunkt mehr.

---

### Phase 2: Deployer Contract Hardening

**Ziel:** Der canonical Deployer-Pfad bekommt stabile, typisierte Deploy-/Destroy-Contracts, zentrale Path Resolution, ein klares SSE-Event-Schema und eine erste route-nahe Error Boundary.

**Implementation Plan:** [`3-cloud-deployer/implementation_plans/2026-04-25_16-11_deployer_contract_hardening.md`](3-cloud-deployer/implementation_plans/2026-04-25_16-11_deployer_contract_hardening.md)

**Reihenfolge:**

1. Deploy-/Destroy-Request- und Result-Contracts definieren.
2. Streaming-Events fuer Deploy/Destroy typisieren.
3. Provider-Normalisierung zentralisieren (`google` als Alias, intern `gcp`).
4. Deployment-Pfade ueber einen zentralen Resolver statt in Routes konstruieren.
5. Deployment-Routes als reine HTTP-Adapter auf Contract Mapping reduzieren.
6. Invalid Provider, Active-Project-Konflikt und Facade-Failures testbar mappen.

**Exit-Kriterien:**

- Deploy/Destroy response shapes sind stabil, getestet und kompatibel.
- SSE event shapes sind stabil und getestet.
- Deployment-Routes bauen keine `/app/upload/{project}`-Pfade mehr manuell.
- Fehler am Deployment-API-Rand sind mindestens nach Validation, Project Conflict und Deployment Failure unterscheidbar.
- Die vollstaendige Entfernung globaler Active-Project-Zustaende bleibt als eigener Folgeschritt sichtbar, falls sie nicht ohne Scope Creep in diese Phase passt.

---

### Phase 3: Repository Hygiene & Documentation Architecture

**Ziel:** Aktive Produktdateien, versionierte Templates, Runtime-Artefakte und Dokumentation werden getrennt, bevor Credential-, Compose- und Deployment-State-Pfade weiter umgebaut werden.

**Konzept:** [`docs/plans/2026-04-26_repository_hygiene_documentation_architecture.md`](docs/plans/2026-04-26_repository_hygiene_documentation_architecture.md)

**Cleanup Plan:** [`docs/plans/2026-04-26_repository_hygiene_cleanup_plan.md`](docs/plans/2026-04-26_repository_hygiene_cleanup_plan.md)

**Reihenfolge:**

1. README-/Docs-/HTML-/Implementation-Plan-Inventar erstellen.
2. `3-cloud-deployer/upload/template` als Deployment-Vorlage klassifizieren und Zielpfad bzw. kurzfristige Absicherung festlegen.
3. Runtime-/Generated-Dateien in `upload/` von Template-Dateien trennen.
4. MkDocs-basierte Docs-Site mit Docker-Dev-Server und Auto-Reload anlegen.
5. Canonical Architektur-, Cloud-Setup- und User-Guide-Dokumente nach `docs-site/docs` migrieren; der Docs-Container liest nur aus `docs-site/`.
6. Obsolete Dokumentation und alte Artefakte loeschen oder klar archivieren.

**Exit-Kriterien:**

- `upload/template` ist entweder nach `templates/deployment_project` migriert oder explizit als Template dokumentiert und abgesichert.
- `upload/` ist nicht mehr gleichzeitig Template-, Runtime- und Development-Ort.
- Eine MkDocs-basierte Docs-Site existiert und kann lokal per Docker mit Auto-Reload gestartet werden.
- `docs-site/` ist die vollstaendige Quelle der publizierten Website; projektlokale Docs duerfen nur Entwicklernotiz, historische Quelle oder Uebergangsduplikat sein.
- README-Dateien verweisen auf die Docs-Site und enthalten keine langen Legacy-Dokumentationsbloecke mehr.
- Historische Dokumente sind als aktiv, archiviert oder geloescht klassifiziert.

---

### Phase 4: Runtime, Credentials & Deployment State Hardening

**Ziel:** Dev-/Demo-/Cloud-Runtime, Credential Source of Truth, Deployment Manifest und generierte Deployment Workspaces werden als ein zusammenhängender Architekturblock geklärt.

**Konzept:** [`docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md`](docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md)

**Reihenfolge:**

1. Roadmap, README und Guardrails auf Credential-SSOT und Compose-Split ausrichten.
2. `compose.yaml` in Basis, Dev, Demo und Cloud-Integration trennen.
3. `CloudConnection`-Domain in der Management API definieren.
4. Admin-Credentials als transienten Bootstrap-Input modellieren; nur begrenzte Deployment-Identitaeten persistieren.
5. Statische Bootstrap-Artefakte fuer AWS, GCP und Azure versionieren.
6. Backend erzeugt canonical `DeploymentManifest`; Deployer materialisiert isolierte Workspaces pro Deployment.
7. Flutter waehlt Cloud Connections und sendet User Intent, keine Deployer-Dateiformate.

**Exit-Kriterien:**

- Default-Compose startet ohne echte Cloud-Credentials.
- Echte Cloud-Integration ist explizit ueber ein Cloud-Profil aktivierbar.
- Keine Admin-Credentials werden persistiert.
- Keine echten Credentials liegen in Repo-Root-Dateien, Upload-Templates oder langfristigen Deployer-Projektordnern.
- Twins referenzieren Cloud Connections statt Credential-Payloads.
- Deployment Workspaces sind ephemer, isoliert und aus DB + Artefakten + Terraform-Modulen rekonstruierbar.

---

### Phase 5: Backend Orchestrator entflechten

**Ziel:** Management API-Routes werden dünn; Orchestrierung wandert in Services.

**Implementation Plan:** [`twin2multicloud_backend/implementation_plans/2026-04-26_10-18_backend_orchestrator_disentanglement.md`](twin2multicloud_backend/implementation_plans/2026-04-26_10-18_backend_orchestrator_disentanglement.md)

**Reihenfolge:**

1. `TwinRepository` einführen und schrittweise `db.query(...)` aus Routes ziehen.
2. `TwinLifecycleService` für State-Transitions einführen.
3. `OptimizerClient` und `DeployerClient` kapseln alle `httpx`-Calls.
4. `DeploymentOrchestrator` übernimmt deploy/destroy/test-deploy/test-destroy.
5. Test-Endpunkte aus `twins.py` herauslösen oder strikt als Dev-Router kapseln.
6. Retry-/Timeout-/Error-Mapping zentral in Clients definieren.

**Exit-Kriterien:**

- `twins.py` enthält nur HTTP-Adapterlogik.
- State-Transitions sind in einer Service-/Domain-Schicht testbar.
- Optimizer/Deployer-Calls laufen ausschließlich über typed clients.

---

### Phase 6: Brain Layer Contracts und Pricing Reliability

**Ziel:** Provider-Berechnungen werden konsistent und erweiterbar.

**Aktueller Stand und Reihenfolge:**

1. [x] Gemeinsames `LayerResult` und Layer-Calculator-Contract einführen (#68).
2. [x] AWS/Azure/GCP anbinden und unsupported Capabilities fail-closed behandeln (#68).
3. [x] Pricing-Fetcher-Fehler, Review-Status und versionierte Pricing-Contracts explizit machen (#69, #81-#86).
4. [ ] Provider-Capability-Modelle über den aktuellen Layer-Contract hinaus vervollständigen (#70).
5. [ ] Zusätzliche Services, Tiers und Provider-Fetcher-Coverage vervollständigen (#31, #32).

**Exit-Kriterien:**

- Keine mehrfachen `LayerResult`-Definitionen. (erfüllt)
- Provider-Layer können über eine gemeinsame Testmatrix geprüft werden. (erfüllt)
- Pricing-Fetch-Failures sind sichtbar und führen nicht still zu falschen Kosten.

---

### Phase 7: Flutter Wizard und Twin Views slicen

**Ziel:** UI-State wird testbar und Feature-bezogen.

**Reihenfolge:**

1. State-Management-Regel dokumentieren: Riverpod für App-/Service-Provider, BLoC für Feature-State-Machines.
2. Wizard in Feature-Slices aufteilen:
   - Shell/Navigation
   - Credentials
   - Optimizer
   - Deployer Config
3. `step3_deployer.dart` in kleinere Panels extrahieren.
4. `twin_overview_screen.dart` in Dashboard, Detail, Deployment-Actions und Logbereiche trennen.
5. API-Responses typisieren; `Map<String, dynamic>` an UI-Grenzen reduzieren.
6. `dev-token` und Dev-Auth explizit an Dev-Profil koppeln.

**Exit-Kriterien:**

- Wizard-Tests können einzelne Steps isoliert prüfen.
- Keine zentrale UI-Datei trägt mehrere Feature-Verantwortlichkeiten.
- Dev-Auth ist nicht mehr stiller Default im Service.

---

## 4. Empfohlene Reihenfolge

| Reihenfolge | Phase | Warum zuerst/danach |
|-------------|-------|---------------------|
| 0 | Assessment bereinigen | Ohne aktuelle Quelle der Wahrheit arbeitet man gegen historische Befunde. |
| 1 | Deployer canonical path | Blockiert die meisten anderen Deployer- und Multi-Cloud-Refactorings. |
| 2 | Deployer contract hardening | Baut direkt auf dem canonical path auf und stabilisiert Cloud-Flows. |
| 3 | Repository Hygiene & Documentation Architecture | Klaert Template-, Runtime-, Docs- und Archiv-Ownership, bevor neue Credential-/Compose-Strukturen darauf aufbauen. |
| 4 | Runtime, Credentials & Deployment State | Muss vor tiefer Flutter-/DB-/Deployment-Arbeit geklaert werden, damit Credentials, Compose-Profile und Deployment-Artefakte nicht weiter historisch wachsen. |
| 5 | Backend Orchestrator | Management API ist die zentrale Integrationsschicht; nach Credential-SSOT werden Clients, States und Manifeste klar. |
| 6 | Brain Layer Contracts | Verbessert Optimizer-Erweiterbarkeit und Ergebnisqualität. |
| 7 | Flutter Slicing | Wichtig, aber nach Credential-SSOT gezielter: Flutter kann dann User Intent und CloudConnection-Auswahl statt Deployer-Dateiformate modellieren. |

---

## 5. Was bewusst nicht mehr als offene Schuld geführt wird

Diese Punkte sind im aktuellen Workspace nicht mehr als offene Architektur-Schuld sichtbar:

- `2-twin2clouds/backend/deprecated_calculation/` ist nicht vorhanden.
- `twin2multicloud_backend/main.py` und `twin2multicloud_backend/rest_api.py` sind nicht vorhanden; echter Entry-Point ist `twin2multicloud_backend/src/main.py`.
- Das Management API hat kein Root-`services/` neben `src/services`; sichtbar ist `twin2multicloud_backend/src/services`.
- Historische Implementation Plans sind jetzt Teil von P0-2 Repository Hygiene und nicht mehr als erledigte Bereinigung klassifiziert.

Hinweis: Doppelte GCP-Credential-Dateien und Repo-Root-Credential-Mounts sind wieder als offene Schuld in P0-3 sichtbar und nicht mehr als erledigt klassifiziert.

---

## 6. Verifikationsbefehle

```bash
# Existenz alter erledigter Findings prüfen
find 2-twin2clouds/backend -maxdepth 2 -type d -name 'deprecated_calculation' -print
find twin2multicloud_backend -maxdepth 2 -type f \( -name 'main.py' -o -name 'rest_api.py' \) -print
find . -maxdepth 2 -type d \( -name 'twin2multicloud_cli' -o -name '!!3-cloud-deployer' \) -print

# God-file-Metriken
wc -l \
  twin2multicloud_backend/src/api/routes/twins.py \
  twin2multicloud_flutter/lib/bloc/wizard/wizard_bloc.dart \
  twin2multicloud_flutter/lib/screens/twin_overview/twin_overview_screen.dart \
  twin2multicloud_flutter/lib/screens/wizard/step3_deployer.dart \
  twin2multicloud_flutter/lib/widgets/calc_form/calc_form.dart \
  3-cloud-deployer/src/api/validation.py \
  3-cloud-deployer/src/providers/terraform/package_builder.py \
  3-cloud-deployer/src/api/functions.py \
  3-cloud-deployer/src/validator.py

# Deployer canonical path / legacy import guard
rg -n "src\.aws|import aws|from aws|TerraformDeployerStrategy|CloudProvider|state\.get_active_project" \
  3-cloud-deployer/src 3-cloud-deployer/tests

# Backend-Orchestrator-Schulden
rg -n "db\.query|httpx\.AsyncClient|ENABLE_TEST_ENDPOINTS|test-deploy|test-destroy" \
  twin2multicloud_backend/src/api/routes twin2multicloud_backend/src/services

# Credential-/Runtime-Schulden
find . -maxdepth 3 -type f \( -name '*credentials*.json' -o -name '*credential*.json' \) -print
rg -n "config_credentials|gcp_credentials|google-credentials|SEED_CREDENTIALS_FILE|SEED_GCP_CREDENTIALS_FILE|upload/template|DeploymentManifest|CloudConnection" \
  compose*.yaml README.md ASSESSMENT.md twin2multicloud_backend 3-cloud-deployer twin2multicloud_flutter

# Frontend-Dev-Auth und interne URLs
rg -n "dev-token|ENABLE_TEST_ENDPOINTS|localhost:5003|localhost:5004|flutter_bloc|riverpod|go_router" \
  compose.yaml twin2multicloud_flutter/lib twin2multicloud_flutter/pubspec.yaml
```
