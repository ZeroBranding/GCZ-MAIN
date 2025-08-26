#  Geheimnis- und Konfigurationsmanagement

Dieses Dokument beschreibt, wie Geheimnisse und Konfigurationen in diesem Projekt verwaltet werden. Es ist entscheidend, diese Richtlinien zu befolgen, um die Sicherheit und Stabilität der Anwendung zu gewährleisten.

## Grundprinzip: Keine Geheimnisse im Code

**Das wichtigste Prinzip lautet: Niemals Geheimnisse (Secrets) direkt in den Code, in Konfigurationsdateien oder in die Git-Historie einchecken.**

Geheimnisse sind z.B.:
- API-Schlüssel (Telegram, OpenAI, etc.)
- Passwörter
- Private Zertifikate
- Jegliche Art von Anmeldeinformationen

## Die `.env`-Datei

Alle Geheimnisse und umgebungsspezifischen Konfigurationen werden über eine `.env`-Datei im Stammverzeichnis des Projekts verwaltet.

### Verwendung

1.  **Vorlage kopieren:** Es gibt eine Vorlagedatei namens `.env.template`. Kopieren Sie diese Datei und benennen Sie sie in `.env` um.
    ```bash
    cp .env.template .env
    ```
2.  **Werte eintragen:** Öffnen Sie die `.env`-Datei und tragen Sie Ihre tatsächlichen Werte für die Platzhalter ein.

Die `.env`-Datei wird von Git ignoriert (siehe `.gitignore`), sodass Ihre Geheimnisse niemals das Repository verlassen.

### Validierung beim Start

Die Anwendung verwendet ein striktes Konfigurationsmodell. Beim Start wird die `.env`-Datei automatisch geladen und validiert. Wenn eine **erforderliche** Variable (wie z.B. `TELEGRAM_BOT_TOKEN`) fehlt, wird die Anwendung sofort mit einer Fehlermeldung beendet, die angibt, welche Variablen fehlen. Dies verhindert, dass die Anwendung in einem unkonfigurierten oder instabilen Zustand startet.

## Umgang in der CI/CD-Umgebung

In einer CI/CD-Umgebung (wie z.B. GitHub Actions) wird die `.env`-Datei nicht verwendet. Stattdessen werden die Geheimnisse als "Environment Secrets" oder "Repository Secrets" in der CI/CD-Plattform konfiguriert. Die Anwendung liest diese dann direkt aus den Umgebungsvariablen, genau wie sie es lokal tun würde.

Die CI-Pipeline enthält außerdem einen Schritt, der das Repository auf versehentlich eingecheckte Geheimnisse überprüft (`detect-secrets`). Ein Push oder Pull Request wird blockiert, wenn ein Geheimnis gefunden wird.
