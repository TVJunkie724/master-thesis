# Aktuelle Architektur-Schulden und Refactoring-Roadmap

**Datum:** 2026-04-24
**Scope:** `2-twin2clouds` (Brain), `3-cloud-deployer` (Muscle), `twin2multicloud_backend` + `twin2multicloud_flutter` (Orchestrator)
**Ziel:** Alle gravierenden Architektur-Schulden benennen, nach Risiko priorisieren und eine Roadmap definieren, um sie schrittweise aufzulösen.

Dieses Dokument beschreibt nur den **aktuellen Befund**. Bereits erledigte Altlasten wie `2-twin2clouds/backend/deprecated_calculation/`, doppelte Backend-Entry-Points im Management API, `google-credentials.json` als Duplikat von `gcp_credentials.json`, und archivierte alte Implementation Plans sind hier nicht mehr als offene Findings enthalten.

---

## 0. Kurzurteil

Das System ist ein funktionierender Research-Prototyp mit einem tragfähigen Kern: Optimizer, Deployer, Management API und Flutter UI greifen grundsätzlich ineinander. Die größten Risiken liegen nicht mehr in fehlenden Dateien oder totem Code, sondern in **uneindeutigen Architektur-Grenzen**, **zu großen Verantwortlichkeits-Clustern** und **nicht gekapselten Integrationspunkten**.

Die erste Schuld, die gelöst werden sollte, ist technisch umgesetzt und Docker-verifiziert:

> **P0: Deployer-Dual-Hierarchie auflösen (`3-cloud-deployer/src/aws/` vs. `3-cloud-deployer/src/providers/aws/`).**

Diese Schuld blockiert fast alle anderen sauberen Refactorings im Deployer: Provider-Strategy, Terraform-Flows, Tests, Fehlerbehandlung, Credentials und Multi-Cloud-Verhalten. Die Phase-1-Implementierung konsolidiert den produktiven Pfad auf `src/providers/*` + `TerraformDeployerStrategy` und ist Docker-verifiziert; der Audit-Review bleibt als Gate offen.

---

## 1. Aktueller Befund nach Projekt

| Projekt | Aktueller Architekturzustand | Größtes Risiko |
|---------|------------------------------|----------------|
| `2-twin2clouds` | Funktionsfähiger Optimizer mit guter Price-Fetcher-Factory, aber duplizierter Layer-Logik und vielen Raw-Dicts. | Provider-/Layer-Kalkulation ist schwer erweiterbar und fehleranfällig. |
| `3-cloud-deployer` | Phase-1-Konsolidierung auf `src/providers/*` + `TerraformDeployerStrategy` ist umgesetzt und Docker-verifiziert; globale Projektzustände und sehr große API-/Validation-Module bleiben. | Expliziter Deployment Context und kleinere API-/Validation-Module. |
| `twin2multicloud_backend` | Management API ist der richtige Orchestrator, aber `twins.py` bündelt CRUD, State Machine, Upload, Deployment, SSE und Test-Flows. | Business-Logik steckt in Routes statt in Services/Domain. |
| `twin2multicloud_flutter` | UI nutzt Riverpod, BLoC, Dio und `go_router`; funktional, aber mit großen Smart Widgets/BLoCs und hardcoded Dev-Auth. | Wizard- und Twin-Views sind schwer testbar und schwer evolutionär zu ändern. |

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

### P0-2: Backend God-Route und fehlende Service-/Domain-Schicht

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

### P0-3: Globale Projektzustände im Deployer

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

### P1-2: Brain Layer-Calculation ohne gemeinsame Abstraktion

**Befund:**
`2-twin2clouds/backend/calculation_v2/layers/{aws,azure,gcp}_layers.py` enthalten je eigene Layer-Result-Typen und ähnliche Berechnungsmuster. `LayerResult` ist mehrfach definiert.

**Warum gravierend:**
Provider-Erweiterungen oder Änderungen an Ergebnisfeldern müssen mehrfach nachvollzogen werden. Das erhöht Drift-Risiko zwischen AWS, Azure und GCP.

**Zielbild:**
Gemeinsame Layer-Contracts:

- ein `LayerResult`
- ein `LayerCalculator`-Protocol oder eine abstrakte Basisklasse
- provider-spezifische Komponenten bleiben austauschbar
- gemeinsame Testmatrix für gleiche Layer über Provider hinweg

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
- optional `compose.prod-like.yaml`

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

### Phase 2: Deployer Context und Error Taxonomy

**Ziel:** Deployer-Flows sind request-/deployment-scoped und fehlerdiagnostisch klar.

**Reihenfolge:**

1. `src/core/state.py` durch expliziten `DeploymentContext` ersetzen.
2. API-Endpoints bekommen Projekt-/Twin-Kontext aus Request oder Pfad, nicht aus globalem Zustand.
3. Credential-Checker und Deployment-Services akzeptieren explizite Context-Objekte.
4. Breite `except Exception`-Blöcke nach und nach durch konkrete Exceptions ersetzen.
5. Zentrale Error-Taxonomie definieren und in API-Responses mappen.

**Exit-Kriterien:**

- Kein produktiver Request hängt am globalen Active Project.
- Fehler sind nach Validierung, Credentials, Provider, Terraform und transienten Integrationsfehlern unterscheidbar.

---

### Phase 3: Backend Orchestrator entflechten

**Ziel:** Management API-Routes werden dünn; Orchestrierung wandert in Services.

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

### Phase 4: Brain Layer Contracts und Pricing Reliability

**Ziel:** Provider-Berechnungen werden konsistent und erweiterbar.

**Reihenfolge:**

1. Gemeinsames `LayerResult` einführen.
2. Layer-Calculator-Contract definieren.
3. AWS/Azure/GCP Layer-Calculators schrittweise an den Contract binden.
4. GCP L4/L5 als bewusst deaktivierte Capability modellieren, nicht als halb sichtbare Option.
5. Pricing-Fetcher-Fehler nicht als `{}` verschlucken; Fehlerstatus explizit propagieren.
6. Pricing-Schema versionieren.

**Exit-Kriterien:**

- Keine mehrfachen `LayerResult`-Definitionen.
- Provider-Layer können über eine gemeinsame Testmatrix geprüft werden.
- Pricing-Fetch-Failures sind sichtbar und führen nicht still zu falschen Kosten.

---

### Phase 5: Flutter Wizard und Twin Views slicen

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
| 2 | Deployer context/errors | Baut direkt auf dem canonical path auf und stabilisiert Cloud-Flows. |
| 3 | Backend Orchestrator | Management API ist die zentrale Integrationsschicht; danach werden Clients und States klar. |
| 4 | Brain Layer Contracts | Verbessert Optimizer-Erweiterbarkeit und Ergebnisqualität. |
| 5 | Flutter Slicing | Wichtig, aber weniger systemisch riskant als Deployer/Backend. |

---

## 5. Was bewusst nicht mehr als offene Schuld geführt wird

Diese Punkte sind im aktuellen Workspace nicht mehr als offene Architektur-Schuld sichtbar:

- `2-twin2clouds/backend/deprecated_calculation/` ist nicht vorhanden.
- `twin2multicloud_backend/main.py` und `twin2multicloud_backend/rest_api.py` sind nicht vorhanden; echter Entry-Point ist `twin2multicloud_backend/src/main.py`.
- Das Management API hat kein Root-`services/` neben `src/services`; sichtbar ist `twin2multicloud_backend/src/services`.
- `google-credentials.json` ist nicht vorhanden; `gcp_credentials.json` bleibt als einzelne GCP-Datei neben `config_credentials.json`.
- Brain Implementation Plans liegen vollständig im Archive; Deployer hat 68 archivierte und 2 top-level persistente Referenzdokumente.

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

# Frontend-Dev-Auth und interne URLs
rg -n "dev-token|ENABLE_TEST_ENDPOINTS|localhost:5003|localhost:5004|flutter_bloc|riverpod|go_router" \
  compose.yaml twin2multicloud_flutter/lib twin2multicloud_flutter/pubspec.yaml
```
