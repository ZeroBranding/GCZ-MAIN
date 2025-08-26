# German Code Zero AI

Ein lokales, Windows-natives Automatisierungssystem für KI-gesteuerte Workflows.

## Prinzipien

- **Lokal-First:** Alle Kernfunktionen laufen auf Ihrer eigenen Hardware.
- **Windows-Nativ:** Entwickelt für Windows 11 ohne WSL, Docker oder andere Abstraktionen.
- **Automatisierungsfokus:** Gebaut für die Orchestrierung von KI-Services und externen APIs.

## Quickstart (Windows)

Folgen Sie diesen Schritten, um das System von Grund auf einzurichten und zu starten.

### 1. Einrichtung der Umgebung

Führen Sie das Haupt-Setup-Skript aus. Es klont externe Repositories (ComfyUI, etc.), erstellt eine virtuelle Python-Umgebung (`.venv`) und installiert alle Abhängigkeiten.

```powershell
.\scripts\win\run_all.ps1
```

### 2. Modelle herunterladen

Laden Sie die KI-Modelle für die verschiedenen Services herunter. Diese Skripte platzieren die Gewichte in den richtigen Verzeichnissen außerhalb des Git-Repositorys.

```powershell
# Erforderlich für Avatar-Videos
.\scripts\win\get_sadtalker_models.ps1
.\scripts\win\get_realesrgan_models.ps1

# Erforderlich für den Agenten und LLM-Funktionen
.\scripts\win\ollama_pull.ps1
.\scripts\win\ollama_create_local_models.ps1
```

### 3. Konfiguration & Geheimnisse (Einmalige manuelle Einrichtung)

**WICHTIG:** Bevor Sie das System starten können, müssen Sie Ihre Geheimnisse und Konfigurationen einrichten.

1.  **`.env`-Datei erstellen:** Kopieren Sie die Vorlage `.env.template` nach `.env`.
    ```
    cp .env.template .env
    ```
2.  **Werte eintragen:** Öffnen Sie die `.env`-Datei und füllen Sie die erforderlichen Werte aus (z.B. `TELEGRAM_BOT_TOKEN`).

Eine detaillierte Anleitung zum Umgang mit Geheimnissen finden Sie in der [Geheimnis- und Konfigurationsmanagement-Dokumentation](docs/security/secrets.md).

- **YouTube:** Platzieren Sie Ihre `client_secret.json`-Datei von der Google Cloud Console im Projekt-Root. Beim ersten Upload öffnet sich ein Browser zur Authentifizierung, wodurch eine `token.json` erstellt wird.

- **TikTok:** Melden Sie sich einmalig über die Kommandozeile an, um eine Session-Datei zu erstellen.
  ```powershell
  # Virtuelle Umgebung aktivieren
  .\.venv\Scripts\Activate.ps1
  
  # Anmelden
  python external/TikTokAutoUploader/cli.py login -n default
  ```

- **Instagram:** Die Anmeldedaten werden aus der `.env`-Datei (`IG_USERNAME`, `IG_PASSWORD`) gelesen. Beim ersten Login wird eine Session-Datei erstellt.

### 4. Externe Dienste starten

Starten Sie die ComfyUI-API. Sie muss im Hintergrund laufen, um Bild- und Video-Workflows auszuführen. Beim ersten Start werden die Stable Diffusion-Modelle heruntergeladen.

```powershell
# ComfyUI im Hintergrund starten
.\scripts\win\start_comfyui.ps1
```

### 5. Telegram Bot starten

Starten Sie den Bot, um mit dem System zu interagieren.

```powershell
# Virtuelle Umgebung aktivieren, falls noch nicht geschehen
.\.venv\Scripts\Activate.ps1

# Bot starten
python telegram_bot.py
```

### 6. Beispiel-Befehle im Telegram-Chat

- `/help`: Zeigt alle verfügbaren Befehle an.
- `/img Ein epischer Sonnenuntergang in den Alpen`
- `/anim Ein Astronaut, der auf einem Pferd auf dem Mond reitet`
- `/mail_list`
- (Antworten Sie auf eine E-Mail aus der Liste mit) `/reply <email_id>`
- (Antworten Sie auf den Entwurf mit) `/confirm <draft_id>`

## Wichtiger Hinweis zu Modellen

**Keine KI-Modelle oder Gewichte werden in diesem Git-Repository gespeichert.** Alle Modelle werden durch die bereitgestellten Skripte in das `external`-Verzeichnis (oder in die Verzeichnisse von Ollama/ComfyUI) heruntergeladen. Das `.gitignore`-File stellt sicher, dass diese großen Dateien ignoriert werden.

## Systemdiagnose

Wenn Sie Probleme haben, führen Sie das `doctor`-Skript aus. Es überprüft, ob alle Konfigurationen, Umgebungsvariablen und externen Tools korrekt eingerichtet sind.

```powershell
.\scripts\win\doctor.ps1
```
