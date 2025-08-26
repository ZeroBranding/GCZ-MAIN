# Projekt Backlog & Technische Schulden

Dieses Dokument listet alle bekannten offenen Aufgaben, Bugs, technischen Schulden und Ideen für zukünftige Verbesserungen auf. Es dient als Roadmap für die Weiterentwicklung des Projekts.

---

## 1. Kritische Architekturanpassungen

Diese Aufgaben betreffen die grundlegende Struktur und die Abhängigkeiten des Projekts und sollten priorisiert werden.

*   **[ ] Vendored Dependencies in `external/` auflösen**
    *   **Problem:** Das `external/`-Verzeichnis enthält komplette Kopien von Drittanbieter-Repositories. Dies führt zu einem aufgeblähten Repository, unklarer Versionierung und erschwert Updates.
    *   **Lösung:** Jedes Unterverzeichnis in `external/` sollte durch ein korrekt konfiguriertes **Git Submodule** ersetzt werden. Dies erfordert Recherche, um die exakten Original-Repositories und Commit-Hashes zu finden.

*   **[ ] `instagrapi`-Abhängigkeitsproblem lösen**
    *   **Problem:** `services/instagram_service.py` benötigt die `instagrapi`-Bibliothek. Diese hat eine feste Abhängigkeit zu Pydantic v1, während das Hauptprojekt auf Pydantic v2 läuft. Dies führt zu einem unlösbaren Konflikt. Der Dienst ist aktuell deaktiviert.
    *   **Lösungsvorschläge:**
        1.  Eine alternative Instagram-Bibliothek finden, die mit Pydantic v2 kompatibel ist.
        2.  Den `instagram_service` in einen eigenen Microservice mit separater Umgebung auslagern und über eine API ansprechen.
        3.  Die `instagrapi`-Bibliothek forken und auf Pydantic v2 aktualisieren.

*   **[ ] Altes Konfigurations-System (`core/config.py`) entfernen**
    *   **Problem:** Mehrere Dienste (`asr_service`, `voice_service`, `phone_service`) verwenden noch das alte, auf Pydantic-Modellen und YAML-Dateien basierende Konfigurationssystem in `core/config.py`. Das neue, robustere System ist `core/env.py`.
    *   **Lösung:** Die verbleibenden Dienste müssen so refaktorisiert werden, dass sie ihre Konfiguration aus `core.env` beziehen. Danach kann `core/config.py` und der `configs/`-Ordner entfernt werden, was die Konfiguration erheblich vereinfacht.

---

## 2. Bugs und fehlende Implementierungen

Diese Punkte betreffen konkrete Fehler oder unvollständige Funktionen.

*   **[ ] Fehlende System-level Abhängigkeiten dokumentieren**
    *   **Problem:** Für die lokale Entwicklung werden System-Bibliotheken wie `ffmpeg` benötigt, damit Python-Pakete wie `av` (eine Abhängigkeit von `faster-whisper`) installiert werden können. Dies ist aktuell nicht für Entwickler dokumentiert.
    *   **Lösung:** Die `README.md` oder ein neues `CONTRIBUTING.md` sollte einen Abschnitt zur Einrichtung der lokalen Entwicklungsumgebung enthalten, der die Installation dieser System-Pakete beschreibt.

*   **[ ] Bestehende Test-Suite reparieren**
    *   **Problem:** Die ursprünglichen Tests im `tests/`-Verzeichnis (außerhalb der von mir hinzugefügten Smoke-Tests) sind größtenteils kaputt und schlagen bei der Ausführung fehl.
    *   **Lösung:** Jeder Testfall muss systematisch überprüft, repariert oder (falls veraltet) entfernt werden.

*   **[ ] `sd_service.upscale` implementieren**
    *   **Problem:** Die Upscale-Funktion im `SDService` wirft einen `NotImplementedError`.
    *   **Lösung:** Die Logik zum Aufrufen eines Upscale-Workflows in ComfyUI muss implementiert werden.

*   **[ ] `agent.run_task` erweitern**
    *   **Problem:** Die `run_task`-Methode im Haupt-Agenten kann aktuell nur `generate_image` als vordefinierten Task ausführen und wirft für alles andere einen `NotImplementedError`.
    *   **Lösung:** Weitere vordefinierte Task-Ketten (z.B. für Animation, E-Mail-Beantwortung) müssen hier implementiert werden, um die LLM-Nutzung für Standardaufgaben zu reduzieren.

---

## 3. Gefundene Code-Kommentare (TODOs, FIXMEs)

Die folgenden Punkte wurden durch eine automatische Suche im Code gefunden und deuten auf unfertige oder problematische Stellen hin. (Die meisten befinden sich im `external/`-Code, aber einige könnten relevant sein).

*   `agent/tools_registry.py`: `NotImplementedError` für nicht unterstützte Execution-Methoden.
*   `services/anim_service.py`: Die `animate_from_prompt`-Methode ist nach den Refactorings nicht mehr funktionsfähig und auskommentiert.
*   Diverse `TODO`s in `external/XTTS` und anderen Bibliotheken, die auf unfertige Features in den Abhängigkeiten hinweisen.

---

## 4. Vorschläge für zukünftige Verbesserungen

*   **Inter-Service-Kommunikation verbessern:** Das in PR 6 eingeführte Queue-System (`core/queues.py`) könnte erweitert werden, um die direkte Initialisierung von Services in anderen Services (z.B. in `telegram_service.py`) vollständig abzulösen.
*   **Konfiguration standardisieren:** Die Konfiguration für `ffmpeg` sollte vereinheitlicht werden (wird aktuell in `avatar_service` hartcodiert und in `anim_service` aus der Umgebung geladen).
*   **Testabdeckung erhöhen:** Nach der Reparatur der Test-Suite sollten Unit- und Integrationstests für die Kern-Business-Logik der Dienste geschrieben werden.
