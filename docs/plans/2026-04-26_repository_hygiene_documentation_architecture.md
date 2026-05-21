# Repository Hygiene & Documentation Architecture

**Datum:** 2026-04-26
**Scope:** Repository root, `3-cloud-deployer`, `docs`, README files, historical implementation plans
**Status:** Konzept / Zielarchitektur

**Cleanup Plan:** [`2026-04-26_repository_hygiene_cleanup_plan.md`](2026-04-26_repository_hygiene_cleanup_plan.md)

---

## 1. Ziel

Twin2MultiCloud braucht vor weiteren Credential-, Compose- und Deployment-State-Aenderungen eine klare Repository-Ownership:

- aktive Produktdateien sind von historischen Artefakten getrennt
- `upload/template` wird als wertvolle Deployment-Vorlage behandelt, nicht als Runtime- oder Development-Ablage
- alle Markdown-Quellen der publizierten Website liegen unter `docs-site/docs`
- alte HTML-Dokumentation wird in eine wartbare Markdown-basierte Dokumentationsseite ueberfuehrt
- READMEs bleiben Einstiegspunkte, aber nicht die einzige Architekturquelle
- `twin2multicloud-latex` bleibt als aktive Thesis-Quelle unveraendert bestehen
- obsolete Dateien werden geloescht oder archiviert, statt unklar im aktiven Tree zu bleiben

---

## 2. Template Ownership

`3-cloud-deployer/upload/template` ist fachlich keine Altlast. Es ist die aus den alten Projekten zusammengesetzte Vorlage fuer ein deploybares Projekt. Die Altlast liegt darin, dass dieselbe Struktur auch fuer Development und Runtime-Uploads benutzt wurde.

Zielbild:

```text
3-cloud-deployer/
  templates/
    deployment_project/
      ...
  upload/
    <runtime-generated-projects>
```

Ownership-Regeln:

- `templates/deployment_project` ist versionierte Vorlage.
- `upload/` ist Runtime-/Generated-Bereich.
- Development darf nicht direkt gegen `upload/template` arbeiten.
- Echte Credentials duerfen langfristig weder in Template noch Upload liegen.
- Platzhalter und `.example`-Dateien sind erlaubt, wenn sie eindeutig nicht geheim sind.

Wenn eine sofortige Verschiebung zu riskant ist, darf `upload/template` kurzfristig bleiben, muss aber dokumentiert und durch Tests als Template, nicht als Credential-/Runtime-Quelle, abgesichert werden. Aktuell gueltige lokale Admin-Credentials in diesem Ordner werden nicht geloescht und nicht automatisch verschoben; lokale Cloud-Tests verwenden `.secrets/local/`, sobald die Betreiberin die benoetigten Dateien manuell dorthin kopiert oder verschoben hat.

---

## 3. Documentation Architecture

Die aktuelle HTML-Dokumentation soll nicht weiter als lose, service-lokale HTML-Sammlung wachsen. Ziel ist eine eigene Docs-Site als Projekt-Wiki.

Empfohlener Stack:

```text
MkDocs + Material for MkDocs
```

Warum MkDocs:

- Markdown-basiert
- leichtgewichtig
- Python-nah und gut passend zum bestehenden FastAPI-/Python-Umfeld
- lokale Auto-Reload-Entwicklung via `mkdocs serve`
- einfach in Docker als Docs-Container betreibbar

Zielstruktur:

```text
docs-site/
  Dockerfile
  mkdocs.yml
  docs/
    index.md
    architecture/
    user-guide/
    cloud-setup/
    api/
    references/
    archive/
```

`docs-site/` ist die vollstaendige Quelle der publizierten Website. Der Docs-Container mountet und liest nur diesen Ordner. Projektlokale Dokumentation darf als Entwicklernotiz, historische Originalquelle oder Uebergangsduplikat bestehen bleiben, ist aber nicht die Quelle der publizierten Website.

Referenz-PDFs sind Teil der publizierten Dokumentation, keine Altlast. Das EDTConf'25 Paper `EDT_25__CloudDT_engineering.pdf` und die Deployer-Thesis `bachelor_digital_twins.pdf` werden in `docs-site/docs/references/` uebernommen und dort stabil verlinkt. Bestehende Kopien in `2-twin2clouds/docs/references/`, `3-cloud-deployer/docs/references/` oder im Repository-Root duerfen erst entfernt werden, wenn alle Links auf die zentrale Docs-Site zeigen und die Dateien identisch verifiziert wurden.

Compose-Ziel:

```text
docs:
  build: ./docs-site
  ports:
    - "5010:8000"
  volumes:
    - ./docs-site:/docs
  command: mkdocs serve --dev-addr=0.0.0.0:8000
```

Die Docs-Site wird lokal unter `http://localhost:5010` erreichbar. Markdown-Aenderungen werden im Dev-Modus automatisch neu geladen.

---

## 4. Cleanup-Klassifikation

Jede historische Datei bekommt vor Loeschung oder Migration eine eindeutige Entscheidung:

| Entscheidung | Bedeutung |
|--------------|-----------|
| keep | bleibt aktiv im aktuellen Produktpfad |
| migrate | wird in neue Struktur ueberfuehrt |
| archive | bleibt als historische Referenz, aber nicht als aktive Quelle |
| delete | ist obsolete und wird entfernt |

Diese Klassifikation gilt besonders fuer:

- alte HTML-Dokumentation
- historische Implementation Plans
- Beispiel-/Template-Dateien
- doppelte Credential-Beispiele
- alte Upload-/Runtime-Artefakte
- README-Abschnitte, die Legacy-Flows beschreiben

---

## 5. Umsetzung in Phasen

### Slice 1: Inventory

- Alle aktiven README-/Docs-/HTML-Dateien inventarisieren.
- `3-cloud-deployer/upload/template` Inhalt klassifizieren.
- Runtime-/Generated-Dateien in `upload/` identifizieren.
- Historische Implementation Plans nach aktiv, archiviert und obsolete trennen.

### Slice 2: Target Structure

- Zielstruktur fuer `templates/deployment_project` festlegen.
- Zielstruktur fuer `docs-site` festlegen.
- Dokumentieren, welche READMEs nur Einstiegspunkte bleiben.
- Entscheiden, welche alten HTML-Seiten migriert, archiviert oder geloescht werden.

### Slice 3: Docs Site Bootstrap

- MkDocs-Projekt unter `docs-site/` anlegen.
- Dockerfile fuer Docs-Site anlegen.
- Erste Navigationsstruktur und Startseite erstellen.
- Bestehende canonical Architekturdocs verlinken oder migrieren.

### Slice 4: Template Separation

- Template-Struktur aus Runtime-Nutzung herausloesen.
- Pfade im Deployer auf klare Template-/Runtime-Begriffe vorbereiten.
- Keine echten Credentials in Template oder Upload zulassen.

### Slice 5: Cleanup Guardrails

- Repo-Checks fuer verbotene Runtime-/Credential-Artefakte vorbereiten.
- README-Abschnitte auf neue Docs-Site und canonical Struktur ausrichten.
- Obsolete Dateien entfernen oder in ein klar markiertes Archiv verschieben.

---

## 6. Exit-Kriterien

- `upload/template` ist entweder nach `templates/deployment_project` migriert oder explizit als Template dokumentiert und abgesichert.
- `upload/` ist nicht mehr gleichzeitig Template-, Runtime- und Development-Ort.
- Eine MkDocs-basierte Docs-Site existiert und kann lokal per Docker mit Auto-Reload gestartet werden.
- README-Dateien verweisen auf die Docs-Site und enthalten keine langen Legacy-Dokumentationsbloecke mehr.
- Historische Dokumente sind als aktiv, archiviert oder geloescht klassifiziert.
- Keine echten Credentials liegen in Template-, Docs- oder Upload-Artefakten.
