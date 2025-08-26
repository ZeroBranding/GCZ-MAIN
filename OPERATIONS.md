# GCZ-MAIN - Betriebshandbuch (Operations Manual)

Dieses Dokument beschreibt die Schritte, die für die Einrichtung, den Betrieb und die Überwachung des GCZ-MAIN-Systems erforderlich sind.

## 1. Voraussetzungen

Stellen Sie sicher, dass die folgende Software auf Ihrem System installiert ist:
-   Git (zur Versionskontrolle)
-   Python (Version 3.10 oder höher)
-   PowerShell (für die Ausführung der Start-Skripte unter Windows)
-   Optional: `ffmpeg` für Videoverarbeitungs-Funktionen.

## 2. Setup & Konfiguration

### Schritt 2.1: Repository klonen

Klonen Sie das Repository auf Ihr lokales System:
```bash
git clone https://github.com/ZeroBranding/GCZ-MAIN.git
cd GCZ-MAIN
```

### Schritt 2.2: Abhängigkeiten installieren

Installieren Sie alle erforderlichen Python-Pakete mit `pip`:
```bash
pip install -r requirements.txt
```

### Schritt 2.3: Umgebungsvariablen konfigurieren

Das System wird über Umgebungsvariablen konfiguriert.
1.  Kopieren Sie die Vorlagedatei `.env.sample` zu einer neuen Datei namens `.env`.
    ```bash
    # Windows (Command Prompt)
    copy .env.sample .env

    # Windows (PowerShell)
    Copy-Item .env.sample .env

    # Linux / macOS
    cp .env.sample .env
    ```
2.  Öffnen Sie die `.env`-Datei in einem Texteditor.
3.  Füllen Sie die erforderlichen Werte aus, insbesondere `TELEGRAM_BOT_TOKEN` und die Anmeldedaten für die Dienste, die Sie verwenden möchten (z.B. `GMAIL_USER`, `GMAIL_PASS`).

## 3. System starten

Um alle Dienste der Anwendung zu starten, führen Sie das Haupt-Startskript aus:
```powershell
# Führen Sie dieses Skript in einer PowerShell-Konsole aus
.\run_all.ps1
```
Dieses Skript führt die folgenden Aktionen aus:
1.  **Startet den ComfyUI-Dienst** im Hintergrund für die Bild- und Videogenerierung.
2.  **Startet den EmailPoller-Dienst** im Hintergrund, um auf neue E-Mails zu prüfen.
3.  **Startet den Telegram-Bot** im Vordergrund. Die Konsole wird von diesem Prozess belegt und zeigt Live-Logs des Bots an.

Um das System zu beenden, drücken Sie `CTRL+C` im `run_all.ps1`-Fenster und schließen Sie die anderen von PowerShell geöffneten Fenster.

## 4. Systemüberwachung (Health & Monitoring)

### Telegram-Befehle

Sie können den Zustand des Bots direkt über Telegram mit den folgenden Befehlen überprüfen:
-   `/health`: Antwortet mit "OK", wenn der Bot läuft und auf Befehle reagiert.
-   `/version`: Antwortet mit dem kurzen Git-Commit-Hash der aktuell laufenden Version, um zu überprüfen, welcher Code deployed ist.

### Prometheus-Endpunkt

Für ein detaillierteres Monitoring stellt das System einen Prometheus-kompatiblen Endpunkt bereit.
-   **URL**: `http://localhost:9090/metrics`
-   **Sicherheit**: Dieser Port ist standardmäßig nur auf `localhost` (127.0.0.1) erreichbar und nicht von extern zugänglich.

## 5. Logging

Alle im Hintergrund laufenden Dienste leiten ihre Ausgaben in das `logs/`-Verzeichnis um.
-   **`logs/comfyui.log`**: Logs des ComfyUI-Dienstes.
-   **`logs/email_poller.log`**: Logs des E-Mail-Polling-Dienstes.

### Log-Format

Die Log-Dateien werden in einem strukturierten **JSON-Format** geschrieben. Dies erleichtert die maschinelle Verarbeitung und Analyse.

**Beispiel für einen Log-Eintrag:**
```json
{
    "timestamp": "2023-10-27 10:30:05,123",
    "level": "INFO",
    "name": "services.email_poller",
    "message": "Found 2 new email(s)."
}
```
