# Fehlersuche

Zuerst:

```bash
local-image-ai-service doctor
local-image-ai-service status
journalctl --user -u local-image-ai -n 100 --no-pager
nvidia-smi
```

## Port bereits belegt

Die bisherige inaktive `imgai-api.service` verwendet ebenfalls 7861 und intern 7862. Der neue Dienst
benutzt 7861 und intern 17861. Beide öffentlichen APIs können nicht gleichzeitig 7861 belegen.
Der neue Dienst beendet bei einem Konflikt keinen fremden Prozess und ändert die alte Unit nicht.

```bash
ss -ltnp 'sport = :7861 or sport = :17861'
```

Den fremden Dienst nur selbst bewusst stoppen oder den **neuen** öffentlichen Port in seiner
Konfiguration ändern und dessen Clients entsprechend konfigurieren. Bestehende Programme werden
nicht automatisch umgestellt.

## GPU belegt / CUDA-Speicher knapp

Beim Start wird fremde CUDA-Compute-Nutzung erkannt und das Modellladen verweigert. Der KDE-Kompositor
bleibt ausgenommen. Bestehende Prozesse werden niemals beendet. Eine erst später gestartete `imgai`-
Generierung kann trotzdem mit dem Dienst konkurrieren. Vor bisheriger CLI-/Benchmark-Nutzung:

```bash
local-image-ai-service stop
```

Nach Ende des anderen Workflows den Dienst bei Bedarf wieder starten. Bei OOM kleinere Bildgröße
verwenden und Logs prüfen; keine automatischen Retries. RAM-Grenzen sind keine VRAM-Reservierung.
`/health` kann weiter erreichbar sein, obwohl `/ready` 503 liefert.

## Fehlende Dateien oder Ladefehler

`doctor` prüft beide Modelle. Absolute Pfade in der privaten JSON-Konfiguration korrigieren.
Keine Modelldatei neu herunterladen, umbenennen oder verschieben. MOSS braucht neben DiT, Encoder und
VAE auch `tokenizer_qwen3.5.json`. Ein Ladefehler wird in `/health.error` und im Journal gemeldet;
keine Wiederholschleife. Nach Korrektur:

```bash
local-image-ai-service restart
```

## CUDA-Laufzeitbibliothek fehlt

Die eigene Runtime benötigt die drei in `runtime/receipt.json` verzeichneten CUDA-Bibliotheken.
`cuda_lib` muss auf den eigenen absoluten Runtime-Lib-Pfad zeigen. Die alte Installation wird nicht
zur Laufzeit als Fallback verwendet. `doctor` muss einen `CUDA0`-Backend melden. Kein stiller CPU-Betrieb.

## 409, 429 oder 504

409: per `use` das gewünschte Modell laden und anschließend den Request wiederholen.
429: laufende Generierung abwarten; es gibt keine Auftragswarteschlange.
504: eigene Runtime wurde gestoppt. Logs prüfen und manuell neu starten. Der Client sollte mehr
Zeit als der Diensttimeout einschließlich Prozessbereinigung erlauben. Stop/Modellwechsel bricht
laufende Requests ab.

## systemd aktiv, aber Modell nicht bereit

`Type=simple` bestätigt nur den gestarteten Adapter. `/ready` oder den wartenden Verwaltungsbefehl
verwenden. Nach Backendfehler bleibt der Adapter zur Diagnose erreichbar. `Restart=no` ist beabsichtigt.
Bei `start-limit-hit` erst Ursache beheben, dann `systemctl --user reset-failed local-image-ai`.

## Dateien, Rechte, Browser und Authentifizierung

Konfiguration und optionalen Key mit `chmod 600` schützen. Fehlerhafte Rechte verhindern den Start.
Ein Browser-Origin wird abgelehnt; API-Clients und serverseitige Open-WebUI-Aufrufe nutzen.
401: korrekten Bearer-Key senden. Der Key wird nicht automatisch von einem Client gespeichert.

## Sicher prüfen, dass alte Projekte unverändert sind

Die Erstinstallation hat einen vollständigen SHA-256-Vergleich angelegt, siehe [Prüfbericht](test-report.md).
Ein späterer Vergleich kann legitime Änderungen durch andere Arbeit melden; nicht automatisch zurücksetzen.
Das Audit-Skript schreibt nur in die ausdrücklich gewählte Manifestdatei und liest die geschützten Wurzeln.

```bash
cd ~/dev/github/local-image-ai-service
python3 scripts/audit.py "$HOME/.cache/local-image-ai-service/audit/before.json" --compare
```
