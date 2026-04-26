# Runtime, Credentials & Deployment State Hardening

**Datum:** 2026-04-26
**Scope:** `compose*.yaml`, `twin2multicloud_backend`, `3-cloud-deployer`, `twin2multicloud_flutter`
**Status:** Konzept / Zielarchitektur

---

## 1. Ziel

Twin2MultiCloud braucht eine klare Architekturgrenze fuer lokale Runtime-Profile, Cloud-Credentials, Deployment-Konfiguration und generierte Deployment-Artefakte.

Der finale Zustand ist:

- Die Management API ist die einzige fachliche Source of Truth fuer Cloud Connections.
- Admin-Credentials werden nie persistiert.
- Cloud Connections werden user-scoped gespeichert und von Twins referenziert.
- Flutter erfasst User Intent, aber keine Deployer-/Terraform-Dateistrukturen.
- Der Deployer arbeitet als isolierter Deployment Executor.
- Terraform bleibt die IaC-Schicht, nutzt aber pro Deployment isolierte Workspaces.
- Compose trennt Dev, Demo und echte Cloud-Integration explizit.

---

## 2. Architekturentscheidung

### 2.1 Credential Source of Truth

Credentials gehoeren nicht in Repo-Root-Dateien, versionierte Deployment-Templates oder Deployer-Projektordner. Die Management API verwaltet Cloud-Zugriffe als `CloudConnection`-Ressourcen.

```text
Flutter
  waehlt oder erstellt Cloud Connections

Management API
  validiert, verschluesselt und persistiert begrenzte Deployment-Identitaeten

Deployer
  erhaelt pro Deployment nur den notwendigen Runtime-Kontext
```

Admin-Credentials sind nur Bootstrap-Material. Sie duerfen in keinem normalen Systemzustand vorkommen:

- nicht in der Datenbank
- nicht in Logs
- nicht in ZIPs
- nicht in Terraform-Modulen
- nicht in versionierten Deployment-Templates
- nicht als Compose-Root-Mount

Persistiert werden nur begrenzte Deployment-Identitaeten oder Referenzen darauf.

---

## 3. Cloud Connection Modell

Eine `CloudConnection` gehoert einem User und beschreibt einen begrenzten Cloud-Zugang.

```text
cloud_connections
  id
  user_id
  provider
  display_name
  cloud_scope
  auth_type
  encrypted_payload
  payload_fingerprint
  validation_status
  last_validated_at
  created_at
  updated_at
```

Provider-spezifische Zielwerte:

| Provider | Bevorzugter persistenter Inhalt | Fallback |
|----------|----------------------------------|----------|
| AWS | Role ARN, External ID, optional AssumeRole-Kontext | verschluesselte begrenzte Access Keys |
| GCP | Service Account Email, Impersonation/WIF-Konfiguration | verschluesselter begrenzter Service Account Key |
| Azure | Tenant ID, Subscription ID, Client ID, Resource Group Scope | verschluesseltes begrenztes Client Secret |

Twins speichern keine Secrets. Sie referenzieren Cloud Connections:

```text
twin_provider_bindings
  twin_id
  layer
  provider
  cloud_connection_id
```

---

## 4. Credential Setup Flow

Beim Erstellen oder Bearbeiten eines Twins waehlt der User vorhandene Cloud Connections aus dem Profil. Wenn keine passende Connection existiert, kann der User eine neue Cloud Connection erstellen.

```text
Twin erstellen
  -> vorhandene CloudConnection waehlen
  -> oder "+ Neue CloudConnection"
      -> Provider und Scope waehlen
      -> Setup-Methode waehlen
      -> begrenzte Deployment-Identity erstellen
      -> Deployment-Identity validieren
      -> CloudConnection speichern
      -> Admin-Credentials verwerfen
```

### Setup-Methode A: Statisches Bootstrap-Skript

Dies ist der bevorzugte Zielpfad fuer die erste saubere Umsetzung.

Das Repository enthaelt versionierte, provider-spezifische Bootstrap-Artefakte:

```text
bootstrap/
  aws/
    bootstrap_deployment_identity.sh
    policy.twin2mc-deployer.json
  gcp/
    bootstrap_deployment_identity.sh
    roles.twin2mc-deployer.yaml
  azure/
    bootstrap_deployment_identity.sh
    role.twin2mc-deployer.json
```

Die App parametrisiert nur wenige Werte:

- Connection Name
- Resource Prefix
- AWS Account ID / Region
- GCP Project ID
- Azure Subscription ID / Resource Group

Die Rechte-Definition bleibt statisch, versioniert, reviewbar und testbar.

### Setup-Methode B: Guided One-Time Admin Setup

Komfortmodus fuer lokale Demo und Thesis-Flow:

1. User laedt Admin-Credentials hoch oder gibt sie ein.
2. Backend nutzt sie nur im aktuellen Request.
3. Backend erstellt eine begrenzte Deployment-Identity.
4. Backend validiert die neue Identity.
5. Backend speichert nur die begrenzte Cloud Connection.
6. Backend verwirft Admin-Credentials sofort.

Dieser Modus braucht harte Guardrails:

- Request Body mit Admin-Secrets wird nicht audit-loggt.
- Admin-Secrets werden nicht in Temp-Dateien geschrieben.
- Admin-Secrets werden nie in DB-Feldern gespeichert.
- Fehlerausgaben enthalten nur redacted Provider-Informationen.

### Setup-Methode C: Bootstrap Delegation

Spaeteres Enterprise-Ziel:

Einmalig wird eine stark begrenzte Bootstrap-Identity erstellt. Diese darf neue Deployment-Identitaeten nur innerhalb fester Grenzen erzeugen, z. B. mit Resource Prefix, Permission Boundary, Resource Group Scope oder Projekt-Scope.

Damit kann Twin2MultiCloud spaeter neue Twin-scoped Identities erstellen, ohne jedes Mal Admin-Credentials anzufordern.

---

## 5. Compose Zielbild

`compose.yaml` darf nicht gleichzeitig Dev-, Demo- und Cloud-Integrationsmodus sein.

Zielstruktur:

```text
compose.yaml              # Basis: Services, Netzwerke, Ports, keine echten Secrets
compose.dev.yaml          # Hot reload, Dev Auth, lokale .secrets, Test-Endpunkte
compose.demo.yaml         # Demo ohne echte Cloud-Deployments
compose.cloud.yaml        # echte Cloud-Integration, explizit aktiviert
```

Lokale Secrets liegen ausschliesslich unter:

```text
.secrets/local/
```

Repo-Root-Dateien wie `config_credentials.json`, `gcp_credentials.json` oder `google-credentials.json` sind nicht der Zielzustand.

---

## 6. Deployment State Zielbild

Dateien sind Deployment-Artefakte, nicht Source of Truth.

```text
DB + Terraform State
  = Systemzustand

Generated deployment workspace
  = abgeleiteter Execution Context
```

Pro Deployment wird ein isolierter Workspace erzeugt:

```text
/tmp/twin2mc/deployments/<deployment_id>/
  manifest.json
  terraform.tfvars.json
  generated/
  packages/
  logs/
  secrets/
```

Der Workspace:

- ist deterministisch aus DB, User-Artefakten und versionierten Terraform-Modulen generierbar
- enthaelt Secrets nur zur Laufzeit
- wird nach definierten Retention-Regeln bereinigt
- ist nie fachliche Source of Truth

---

## 7. Deployment Manifest

Flutter erstellt keinen Deployer-Ordner und keine Terraform-Dateien. Flutter sendet User Intent.

Die Management API erzeugt daraus ein canonical `DeploymentManifest`:

```text
DeploymentManifest
  deployment_id
  twin_id
  provider_bindings
  layer_configuration
  artifact_refs
  cloud_connection_refs
  terraform_module_version
  execution_options
```

Der Deployer akzeptiert langfristig nur dieses Manifest plus Runtime Credential Context.

---

## 8. Umsetzung in Phasen

### Slice 1: Roadmap und Guardrails

- `ASSESSMENT.md` aktualisieren.
- Credential- und Compose-Zielbild dokumentieren.
- Forbidden-path Tests fuer echte Credential-Artefakte vorbereiten.
- README als Dev-/Demo-/Cloud-Profile ausrichten.
- Repository-Hygiene-Phase als Voraussetzung abgeschlossen halten.

### Slice 2: Compose Split

- Basis-Compose von Dev-/Demo-/Cloud-Modi trennen.
- Root-Credential-Mounts aus Default-Pfad entfernen.
- `.secrets/local` als einzige lokale Secret-Quelle fuer Dev dokumentieren.
- Mock/Test-Endpunkte nur im Dev-Profil aktivieren.

### Slice 3: CloudConnection Domain

- DB-Modelle und Migrationen fuer Cloud Connections einfuehren.
- Encryption Service zentralisieren.
- Redacted API Responses definieren.
- Existing-credential Import als Compatibility Path bereitstellen.

### Slice 4: Bootstrap v1

- Statische Bootstrap-Artefakte fuer AWS, GCP und Azure anlegen.
- Parameter-Contracts definieren.
- Output-Format fuer App-Import vereinheitlichen.
- Validierung pro Provider an CloudConnection binden.

### Slice 5: Deployment Manifest und Workspace

- Backend erzeugt `DeploymentManifest`.
- Deployer materialisiert isolierte Workspaces pro Deployment.
- Credentials werden nur noch runtime-lokal materialisiert.
- Credential-Dateien werden aus Upload- und Template-Pfaden entfernt.

### Slice 6: Flutter Integration

- Wizard waehlt Cloud Connections statt Secret-Felder pro Twin zu speichern.
- `+ Neue CloudConnection` wird eigener Setup-Flow.
- Twin-Konfiguration referenziert Cloud Connections und Provider-Bindings.
- UI zeigt nur Status, Scope und Redacted Metadata.

---

## 9. Exit-Kriterien

- Keine echten Credentials liegen im Repo-Root, in Upload-Pfaden oder in versionierten Deployment-Templates.
- Default-Compose startet ohne echte Cloud-Credentials.
- Cloud-Modus ist explizit und nutzt `.secrets/local` oder CloudConnection-basierte Runtime-Kontexte.
- Admin-Credentials werden durch Tests und Code-Review-Regeln von Persistenz ausgeschlossen.
- Twins referenzieren Cloud Connections statt Credential-Payloads zu besitzen.
- Der Deployer liest Credentials nicht mehr aus statisch gemounteten Repo-Dateien.
- Deployment Workspaces sind pro Deployment isoliert und bereinigbar.
- Flutter sendet User Intent; Backend erzeugt canonical Deployment Manifests.
