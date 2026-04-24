---
title: "Konzept — Enterprise Target Architecture"
description: "Finales Zielbild fuer eine saubere, enterprise-grade Twin2MultiCloud Architektur."
tags: [concept, architecture, enterprise, clean-architecture, twin2multicloud]
lastUpdated: "2026-04-24"
version: "1.0"
---

<!-- SOURCES:
- integration_vision.md §3 "System Architecture"
- integration_vision.md §4 "The Management Platform (Vision)"
- FRONTEND_ARCHITECTURE.md §Architecture Overview
- FRONTEND_ARCHITECTURE.md §5 "File Versioning: DB as Truth, Files via Deployer API"
- ASSESSMENT.md §3 "Roadmap"
- User decision 2026-04-24: Ziel ist enterprise-grade Code, keine Master-Thesis-Abkuerzungen im Zielbild
EXTRACTED: 2026-04-24 | VERSION: 1.0
-->

# Konzept — Enterprise Target Architecture

Dieses Konzept beschreibt ausschliesslich den finalen Zielzustand der Twin2MultiCloud Architektur: **wie das System aussehen soll**, **warum diese Struktur enterprise-grade ist** und welche Architekturregeln fuer kuenftige Umsetzung verbindlich sind.

---

## Zusammenfassung

Twin2MultiCloud besteht final aus vier klar getrennten Bounded Contexts:

| Context | Rolle | Verantwortung |
|---------|-------|---------------|
| `twin2multicloud_flutter` | Experience Layer | User Interaction, Desktop/Web UI, lokale UI-State-Machines |
| `twin2multicloud_backend` | Management / Orchestrator | Auth, Users, Twins, Lifecycle, Persistenz, API-Facade, Integration |
| `2-twin2clouds` | Optimization Brain | Kostenmodelle, Pricing, Provider-Auswahl, mathematische Optimierung |
| `3-cloud-deployer` | Deployment Muscle | Infrastructure-as-Code, Cloud-Provider-Provisioning, Destroy, Outputs |

Die zentrale Architekturentscheidung lautet:

> Das Management API ist die einzige Orchestrierungsgrenze. Flutter spricht nur mit dem Management API. Optimizer und Deployer bleiben fachlich eigenstaendige Services, werden aber ausschliesslich ueber explizite, typisierte Clients vom Management API konsumiert.

---

## Scope

| In scope ✅ | Out of scope ❌ |
|------------|----------------|
| Zielarchitektur fuer alle vier Twin2MultiCloud-Projekte | Audit- oder Backlog-Dokumentation |
| Enterprise-grade Schichten, Verantwortungen und Grenzen | Detaillierte Implementierungsplaene |
| Service-, Repository-, Client- und Domain-Zielbild | Konkrete Klassen- oder Widget-Baum-Entscheidungen |
| Qualitaetsbarrieren fuer Security, Tests, Observability und Environments | Kurzfristige Demo-Abkuerzungen |
| Architekturprinzipien fuer kuenftige Refactoring-Phasen | Migration einzelner Dateien |

---

## Architekturzielbild

```
┌──────────────────────────────────────────────────────────────────────┐
│ Experience Layer                                                     │
│ twin2multicloud_flutter                                              │
│ - Desktop/Web UI                                                     │
│ - Feature State Machines                                             │
│ - Typed API Models                                                   │
│ - HTTP + SSE only to Management API                                  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               │ HTTPS / SSE
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Management / Orchestrator                                            │
│ twin2multicloud_backend                                              │
│ - Auth + users                                                       │
│ - Twin lifecycle                                                     │
│ - Versioned configuration                                            │
│ - Deployment orchestration                                           │
│ - Typed OptimizerClient + DeployerClient                             │
│ - Repository + domain services                                       │
└───────────────┬──────────────────────────────────────┬───────────────┘
                │                                      │
                │ Typed REST                           │ Typed REST / SSE bridge
                ▼                                      ▼
┌──────────────────────────────┐       ┌───────────────────────────────┐
│ Optimization Brain            │       │ Deployment Muscle              │
│ 2-twin2clouds                 │       │ 3-cloud-deployer               │
│ - Pricing contracts           │       │ - Provider contracts           │
│ - Layer calculators           │       │ - Terraform strategy           │
│ - Cost result DTOs            │       │ - Explicit deployment context  │
│ - Deterministic optimization  │       │ - Provider outputs             │
└──────────────────────────────┘       └───────────────────────────────┘
```

Warum das enterprise-grade ist:

1. **Klare Ownership:** Jeder Context besitzt genau eine fachliche Aufgabe.
2. **Explizite Grenzen:** Kommunikation laeuft ueber definierte API-Contracts, nicht ueber geteilte Implementierungsdetails.
3. **Austauschbarkeit:** Optimizer und Deployer koennen intern refactored werden, solange ihre Contracts stabil bleiben.
4. **Testbarkeit:** Jede Schicht kann isoliert getestet werden; Integrationsrisiken werden ueber Contract Tests sichtbar.
5. **Betriebssicherheit:** Auth, State, Logs, Retries und Fehlerklassifikation liegen an der Orchestrierungsgrenze.

---

## Architekturprinzipien

### 1. Single Canonical Path

Jeder fachliche Flow hat genau einen produktiven Pfad. Fuer Deployments bedeutet das:

```
Flutter → Management API → Deployer API → Provider Strategy → Terraform
```

Es gibt keine parallelen produktiven Implementierungen desselben Flows. Alternative Implementierungen duerfen nur existieren, wenn sie explizit als Adapter, Test Double oder experimenteller Spike isoliert sind.

**Warum:** Enterprise-Systeme brauchen Vorhersagbarkeit. Wenn zwei Pfade dieselbe Verantwortung tragen, entstehen Drift, doppelte Bugs und unklare Testaussagen.

### 2. Thin Adapters, Rich Services

HTTP-Routes, Flutter Widgets und CLI-/Script-Entrypoints sind Adapter. Adapter validieren Request/Response-Form, delegieren an Services und enthalten keine fachliche Orchestrierung.

Fachlogik lebt in Services, Domain-Objekten und Clients:

| Ebene | Verantwortung |
|-------|---------------|
| Adapter | HTTP, UI, command entry, request parsing |
| Application Service | Use Cases, Orchestrierung, Transaktionen |
| Domain | State Machine, Invarianten, fachliche Regeln |
| Infrastructure | DB, HTTP Clients, Terraform, Cloud SDKs |

**Warum:** Fachlogik wird dadurch testbar, wiederverwendbar und entkoppelt von Frameworks.

### 3. Explicit Context, No Global Mutable State

Jeder Deploy-, Destroy-, Validate- oder Optimize-Flow bekommt einen expliziten Context. Dieser Context enthaelt alle notwendigen Informationen wie Twin-ID, User-ID, Provider-Auswahl, Credentials-Referenzen, Deployment-ID und Correlation-ID.

**Warum:** Expliziter Context macht parallele Requests, mehrere Nutzer und mehrere Twins sicher. Globale mutable States verhindern saubere Isolation und fuehren zu schwer reproduzierbaren Fehlern.

### 4. Typed Contracts At Every Boundary

Alle Grenzen verwenden explizite Request-/Response-Modelle:

| Grenze | Contract-Form |
|--------|---------------|
| Flutter → Management API | Dart Models + JSON serialization |
| Management API → Optimizer | Pydantic DTOs + typed `OptimizerClient` |
| Management API → Deployer | Pydantic DTOs + typed `DeployerClient` |
| Deployer → Cloud Provider | Provider Protocols + Deployment Context |
| Optimizer intern | Pricing DTOs + Layer Result Contracts |

**Warum:** Typed Contracts machen Schema-Drift sichtbar, verbessern IDE-Unterstuetzung und erlauben Contract Tests.

### 5. Observable By Design

Jeder systemuebergreifende Flow hat eine Correlation-ID. Logs, Deployment-Events, API-Responses und SSE-Events koennen derselben Operation zugeordnet werden.

Finale Observability-Bausteine:

| Baustein | Ziel |
|----------|------|
| Structured JSON logs | Maschinenlesbare Analyse |
| Correlation-ID | End-to-end Nachvollziehbarkeit |
| Deployment event stream | UI-Feedback und Audit Trail |
| Error taxonomy | Klare Fehlerursachen |
| Timing metadata | Performance- und Timeout-Analyse |

**Warum:** Cloud-Deployment ist fehleranfaellig. Enterprise-grade bedeutet, dass Fehler nicht nur auftreten, sondern erklaerbar und reproduzierbar sind.

---

## Zielbild pro Context

### Experience Layer: `twin2multicloud_flutter`

Flutter ist die Experience-Schicht, nicht die Orchestrierungsschicht.

Finale Regeln:

| Regel | Begruendung |
|-------|-------------|
| Flutter spricht nur mit dem Management API. | Interne Service-Topologie bleibt verborgen. |
| App-/Service-Dependencies werden zentral injiziert. | Tests koennen Provider/Clients ersetzen. |
| Feature-State-Machines sind klein und fachlich begrenzt. | Wizard, Dashboard und Detail-Views bleiben testbar. |
| API-Daten werden in typed Models gewandelt. | UI arbeitet nicht mit Raw JSON. |
| Dev-Auth ist ein explizites Dev-Profil. | Demo-Komfort wird nicht zum Produktstandard. |

Finaler Datenfluss:

```
Widget → Feature State → Repository/API Service → Management API
       ← Typed Model     ← Typed Response        ← Domain Result
```

### Management / Orchestrator: `twin2multicloud_backend`

Das Management API ist die fachliche Mitte des Systems.

Finale Module:

| Modul | Verantwortung |
|-------|---------------|
| `TwinRepository` | Persistenzzugriff fuer Twins, Deployments, Logs |
| `TwinLifecycleService` | Zulaessige State-Transitions und Invarianten |
| `ConfigurationService` | Versionierte Optimizer-/Deployer-Konfiguration |
| `DeploymentOrchestrator` | Deploy/Destroy Use Cases |
| `OptimizerClient` | Alle Calls zum Optimizer |
| `DeployerClient` | Alle Calls zum Deployer |
| `AuthService` | User, JWT, OAuth/SAML Provider |
| `EventStreamService` | SSE, Logs, Deployment Events |

Warum diese Struktur:

- Routes bleiben stabil und klein.
- Domain-Regeln sind ohne FastAPI testbar.
- Integrationsfehler werden an Clients gekapselt.
- State-Transitions sind explizit und auditierbar.

### Optimization Brain: `2-twin2clouds`

Der Optimizer ist ein deterministischer Berechnungsservice.

Finale Regeln:

| Regel | Begruendung |
|-------|-------------|
| Pricing-Daten haben versionierte Schemas. | Berechnungsergebnisse bleiben nachvollziehbar. |
| Layer-Ergebnisse folgen einem gemeinsamen Contract. | Provider koennen konsistent verglichen werden. |
| Provider-spezifische Formeln sind isoliert. | Neue Provider/Services veraendern keine fremden Provider. |
| Fetching-Fehler werden explizit gemeldet. | Keine still falschen Kosten durch leere Defaults. |
| Optimierung ist reproduzierbar. | Thesis-Ergebnisse und Regression Tests bleiben vergleichbar. |

Finaler Flow:

```
OptimizationRequest
  → validate scenario
  → load pricing snapshot
  → calculate provider/layer candidates
  → rank deterministic result
  → return OptimizationResult with evidence metadata
```

### Deployment Muscle: `3-cloud-deployer`

Der Deployer ist ein provider-neutraler Provisioning-Service mit provider-spezifischen Strategien.

Finale Module:

| Modul | Verantwortung |
|-------|---------------|
| `DeploymentContext` | Vollstaendiger, expliziter Kontext eines Deployments |
| `ProviderRegistry` | Auswahl und Erzeugung der Cloud Provider |
| `CloudProvider` Protocol | Einheitlicher Provider-Vertrag |
| `TerraformDeployerStrategy` | IaC-Ausfuehrung und Lifecycle |
| Provider Modules | AWS/Azure/GCP-spezifische Ressourcenlogik |
| `CredentialValidationService` | Provider-spezifische Credential-Pruefung |
| `DeploymentResult` | Typed Outputs, Resource IDs, Status |

Finaler Flow:

```
DeployRequest
  → create DeploymentContext
  → validate credentials and config
  → resolve providers per layer
  → build terraform package
  → plan/apply
  → collect typed outputs
  → emit deployment events
```

Warum diese Struktur:

- Provider-spezifische Unterschiede bleiben hinter einem Contract.
- Terraform bleibt die einzige IaC-Ausfuehrungsschicht.
- Jeder Deployment-Lauf ist durch Context und Result auditierbar.
- Parallele Deployments sind strukturell moeglich.

---

## Enterprise Quality Gates

Jede kuenftige Umsetzung muss diese Gates erfuellen, bevor sie als abgeschlossen gilt.

| Gate | Erwartung |
|------|-----------|
| Architecture | Genau eine fachliche Verantwortung pro Modul/Service |
| Contracts | Jede Systemgrenze hat typed DTOs |
| Tests | Unit-, integration- und contract-relevante Tests fuer geaenderte Flows |
| Errors | Fehler sind klassifiziert, nicht pauschal verschluckt |
| Observability | Correlation-ID und strukturierte Logs fuer systemuebergreifende Flows |
| Security | Secrets und Dev-Auth sind nicht impliziter Default |
| Config | Dev, demo und prod-like Environments sind getrennt |
| Documentation | Zielbild, Entscheidungen und Exit-Kriterien sind dokumentiert |

---

## Error Taxonomy

Das finale System unterscheidet Fehler fachlich, nicht nur technisch.

| Fehlerklasse | Bedeutung | Typische Behandlung |
|--------------|-----------|---------------------|
| `ValidationError` | Eingaben oder Konfiguration sind ungueltig | User-korrigierbar anzeigen |
| `CredentialError` | Provider-Zugangsdaten fehlen oder sind ungueltig | Credential-Setup fuehren |
| `ProviderError` | Cloud Provider lehnt Operation ab | Provider-spezifisch erklaeren |
| `TerraformError` | IaC plan/apply/destroy scheitert | Deployment abbrechen, Logs verlinken |
| `TransientIntegrationError` | Timeout, Netzwerk, temporaerer Servicefehler | Retry/backoff, danach kontrolliert fehlschlagen |
| `DeploymentStateError` | Operation passt nicht zum Twin-/Deployment-State | State-Konflikt erklaeren |
| `SystemError` | Unerwarteter interner Fehler | Correlation-ID ausgeben, intern loggen |

Warum:

- UI kann bessere Meldungen zeigen.
- Tests koennen erwartete Fehlerpfade pruefen.
- Logs werden auswertbar.
- Retry-Entscheidungen werden regelbasiert.

---

## Environment Model

Final gibt es getrennte Environment-Profile.

| Profil | Zweck | Eigenschaften |
|--------|------|---------------|
| `dev` | lokale Entwicklung | Dev-Auth erlaubt, Test-Endpunkte explizit aktivierbar |
| `demo` | Thesis-/Defense-Demo | stabile Defaults, Mock-Deploy optional sichtbar gekennzeichnet |
| `prod-like` | produktionsnahe Validierung | echte Auth, keine Test-Endpunkte, Secrets nur ueber Environment/Secret Store |

Warum:

Demo-Komfort und Produktqualitaet duerfen sich nicht gegenseitig verstecken. Ein enterprise-grade System darf Dev-Erleichterungen haben, aber sie muessen explizit, isoliert und abschaltbar sein.

---

## Testing Strategy

Das Zielbild verwendet Tests als Architekturbarriere, nicht als nachtraegliche Absicherung.

| Testtyp | Zweck |
|---------|------|
| Unit Tests | Domain-Regeln, State Machines, Provider-Logik |
| Service Tests | Orchestrator-Use-Cases ohne echte HTTP-/DB-Seiteneffekte |
| Contract Tests | Management API ↔ Optimizer/Deployer DTO-Kompatibilitaet |
| Integration Tests | Service-Flows gegen lokale Docker-Services |
| UI Tests | Kritische Flutter-Wizard- und Deployment-Flows |
| No-real-cloud default | Echte Cloud-Ressourcen nur mit expliziter Freigabe |

Warum:

Enterprise-grade Refactoring ist nur sicher, wenn Architekturgrenzen durch Tests bewacht werden. Besonders wichtig sind Contract Tests, weil Twin2MultiCloud aus mehreren Services besteht.

---

## Architecture Decision Summary

| Entscheidung | Finaler State | Warum |
|--------------|---------------|-------|
| Orchestrierung | Management API ist einziger Orchestrator | Zentrale Auth, Persistenz, Lifecycle-Kontrolle |
| Frontend-Zugriff | Flutter spricht nur mit Management API | Keine Client-Kopplung an interne Services |
| Deployment | Ein provider-neutraler Deployer-Pfad | Keine Drift zwischen parallelen Implementierungen |
| Provider | Provider Contracts + Registry | Erweiterbarkeit ohne Cross-Provider-Chirurgie |
| State | Expliziter Context statt globale Projektzustandswerte | Parallelitaet und Testbarkeit |
| Persistenz | Repository-Schicht statt ORM in Routes | Austauschbarkeit und isolierte Tests |
| Integration | Typed Clients statt rohe HTTP-Calls in Routes | Retry, Fehler-Mapping, Contract Tests |
| Fehler | Gemeinsame Error Taxonomy | User Feedback, Logs, Retry-Strategie |
| Observability | Correlation-ID + structured logs | Diagnose ueber Servicegrenzen hinweg |

---

## Beziehung zur Roadmap

Dieses Konzept definiert den finalen Zustand. Die konkrete Reihenfolge der Refactoring-Arbeit ist in [ASSESSMENT.md](../../ASSESSMENT.md) als Roadmap festgehalten.

Die Roadmap darf technische Zwischenschritte enthalten. Dieses Konzept darf keine Zwischenarchitektur legitimieren. Wenn eine Zwischenloesung vom Zielbild abweicht, muss sie zeitlich begrenzt, dokumentiert und durch ein klares Exit-Kriterium abgesichert sein.

---

## Akzeptanzkriterien fuer das Zielbild

Das Zielbild gilt als erreicht, wenn folgende Aussagen wahr sind:

- Flutter kann keinen Optimizer- oder Deployer-Service direkt adressieren.
- Das Management API besitzt typed Clients fuer Optimizer und Deployer.
- Deployment-Flows laufen ueber einen einzigen provider-neutralen Pfad.
- Jeder Deployment-Lauf besitzt einen expliziten `DeploymentContext`.
- Domain-State-Transitions sind ausserhalb von HTTP-Routes testbar.
- Optimizer-Layer-Ergebnisse folgen einem gemeinsamen Contract.
- Dev-/Demo-/Prod-like-Konfigurationen sind getrennt.
- Fehler sind klassifiziert und werden mit Correlation-ID geloggt.
- Kritische Systemgrenzen haben Contract Tests.
- Dokumentation beschreibt Zielzustand und Entscheidungen.
