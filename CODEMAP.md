# CODEMAP: Übersicht über die GCZ-MAIN Architektur

Dieses Dokument bietet einen Überblick über die Codebasis des GCZ-MAIN-Projekts, seine Architektur und die wichtigsten Komponenten. Es soll Entwicklern und Betreibern helfen, sich schnell im Projekt zurechtzufinden.

## 1. High-Level-Übersicht

GCZ-MAIN ist ein multi-agentenbasiertes System, das darauf ausgelegt ist, verschiedene Aufgaben der Inhaltserstellung und -verarbeitung zu automatisieren. Es integriert eine Reihe von spezialisierten Diensten (Services) für Aufgaben wie E-Mail-Verarbeitung, Text-zu-Bild-Generierung (Stable Diffusion), Sprachsynthese und Interaktion über Telegram.

Das System ist modular aufgebaut und wird durch Konfigurationsdateien und definierte Workflows gesteuert.

## 2. Architektur-Komponenten

Die Architektur besteht aus mehreren losely-gekoppelten Hauptkomponenten:

-   **Entry Points & Runner**: PowerShell-Skripte (`.ps1`), die für den Start und die Verwaltung der verschiedenen Dienste verantwortlich sind. Der primäre Einstiegspunkt ist `run_all.ps1`.
-   **Services**: Eigenständige Python-Skripte im `services/`-Verzeichnis, die die Kernlogik für spezifische Aufgaben kapseln (z.B. `EmailService`, `SDService`, `TelegramService`).
-   **Core-Engine**: Gemeinsame Funktionalitäten im `core/`-Verzeichnis, einschließlich Konfigurations-Lader, Logging, Workflow-Engine und Fehlerbehandlung.
-   **Agents**: Autonome Agenten im `agents/`-Verzeichnis, die in der Lage sind, komplexe Aufgaben zu planen und auszuführen, indem sie verschiedene Dienste und Werkzeuge koordinieren.
-   **Workflows**: YAML-definierte Abläufe im `flows/`-Verzeichnis, die von der `WorkflowEngine` ausgeführt werden, um Aufgaben zu orchestrieren (z.B. `sd_generate.yml`).
-   **Konfiguration**: YAML-Dateien im `configs/`-Verzeichnis, die das Verhalten der einzelnen Dienste und Agenten steuern. Zusätzlich wird eine `.env`-Datei für sensible Daten und Umgebungsvariablen verwendet.
-   **Externe Abhängigkeiten**: Das `external/`-Verzeichnis enthält eine Reihe von eingebetteten (vendored) Drittanbieter-Tools wie `ComfyUI`, `OpenVoice` und `XTTS`. Dies ist eine technische Schuld, die im Rahmen des Refactorings adressiert werden sollte, z.B. durch die Umstellung auf Git Submodules oder Paketmanagement.

## 3. Verzeichnisstruktur

Hier ist eine Aufschlüsselung der wichtigsten Verzeichnisse:

-   **/ (Root)**: Enthält die Haupt-Entry-Points (`run_all.ps1`), Konfigurationsdateien (`pyproject.toml`, `requirements.txt`) und dieses `CODEMAP.md`.
-   **`agents/`**: Definiert die Logik der autonomen Agenten.
-   **`configs/`**: Enthält anwendungsspezifische Konfigurationen im YAML-Format.
-   **`core/`**: Beherbergt den zentralen, wiederverwendbaren Code für Logging, Monitoring, Sicherheit und die Workflow-Engine.
-   **`external/`**: Enthält Kopien von externen Repositories. **Achtung:** Dies ist problematisch für die Wartung und sollte geändert werden.
-   **`flows/`**: Definiert mehrstufige Prozesse, die von der Workflow-Engine ausgeführt werden können.
-   **`runbooks/` & `scripts/`**: Sammlung von PowerShell-Skripten zur Automatisierung von Setup, Betrieb und Wartung.
-   **`services/`**: Implementiert die Geschäftslogik der einzelnen Microservices (E-Mail, Stable Diffusion, Telegram etc.).
-   **`tests/`**: Enthält Unit-, Integrations- und Smoke-Tests zur Sicherstellung der Codequalität.

## 4. Einstiegspunkte (Entry Points)

-   **Haupt-Skript**: `run_all.ps1` im Root-Verzeichnis ist das primäre Skript, um alle Dienste des Systems zu starten.
-   **Einzelne Runner**: Die Skripte in `runbooks/` und `scripts/win/` werden verwendet, um einzelne Dienste oder Aufgaben manuell zu starten (z.B. `run_telegram.ps1`).

## 5. Konfiguration

Die Konfiguration des Systems erfolgt über zwei Mechanismen:
1.  **YAML-Dateien** in `configs/`: Für statische, nicht-sensible Konfigurationen der Dienste.
2.  **`.env`-Datei**: Für sensible Daten wie API-Keys, Passwörter und umgebungsspezifische Einstellungen. Diese Datei wird nicht ins Git eingecheckt. Stattdessen dient eine `.env.sample`-Datei als Vorlage.

## 6. Technische Schulden & Nächste Schritte

### Eingebettete Abhängigkeiten im `external/` Verzeichnis

Das `external/`-Verzeichnis enthält vollständige Kopien von Drittanbieter-Bibliotheken (u.a. ComfyUI-Manager, OpenVoice, XTTS). Dies wird als "Vendoring" bezeichnet und stellt eine erhebliche technische Schuld dar:
-   **Keine Versionskontrolle**: Es ist unklar, welche Version (Commit-Hash) der jeweiligen Bibliothek verwendet wird.
-   **Schwierige Updates**: Das Aktualisieren dieser Abhängigkeiten ist ein manueller und fehleranfälliger Prozess.
-   **Aufgeblähtes Repository**: Das Repository wird durch das Einchecken von tausenden fremden Dateien unnötig groß.

**Empfohlene Lösung:**
Jede dieser Abhängigkeiten sollte in einem eigenen, dedizierten Pull Request durch einen korrekten **Git Submodule** ersetzt werden.

```bash
# Beispiel für die Umwandlung
git rm -r external/ComfyUI-Manager
git submodule add https://github.com/ltdrdata/ComfyUI-Manager external/ComfyUI-Manager
```

Dieser Prozess muss für jede Bibliothek im `external/`-Verzeichnis sorgfältig durchgeführt werden, um die Funktionalität des Systems nicht zu beeinträchtigen. Fürs Erste wurde das `external/`-Verzeichnis in die `.gitignore` aufgenommen, um weitere Änderungen an diesem Code zu verhindern.
