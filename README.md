# Local Image AI Service

Eigenständiger lokaler Image-Inference-Dienst für **MOSS-Image SFT** und **Z-Image Turbo**.
MOSS ist der Standard. Kein Import und kein Aufruf von `imgai`, kein Spiel-, Blender- oder Track-Code.

Stand 28.10.2026: installiert und mit beiden Modellen auf Fedora 44 / RTX 5070 Laptop 8 GB geprüft.
Der Dienst ist nach den Tests **gestoppt**, ohne Login-Autostart. Kein Remote-Repository wurde angelegt.

```bash
local-image-ai-service doctor
local-image-ai-service start
local-image-ai-service status
local-image-ai-service models
local-image-ai-service use z-image
local-image-ai-service use moss
local-image-ai-service logs
local-image-ai-service stop
```

Alternativ direkt:

```bash
systemctl --user start local-image-ai
systemctl --user stop local-image-ai
systemctl --user restart local-image-ai
systemctl --user status local-image-ai
journalctl --user -u local-image-ai -f
```

Die Verwaltungsbefehle `start`, `restart` und `use` warten zusätzlich auf Modellbereitschaft.
Bei direktem `systemctl start` erfolgt das Laden im Hintergrund; `/ready` prüfen.

API: `http://127.0.0.1:7861/v1`. Ohne konfigurierten API-Key lokal ohne Authentifizierung.

```bash
curl --fail-with-body http://127.0.0.1:7861/v1/models
curl --fail-with-body http://127.0.0.1:7861/v1/images/generations \
  -H 'Content-Type: application/json' \
  -d '{"model":"moss","prompt":"A red teapot on a white table","seed":42,"size":"512x512","n":1,"response_format":"b64_json"}'
```

Die Antwort enthält PNG-Daten in `data[0].b64_json`. Es erfolgt keine automatische Bildspeicherung.
Eine gleichzeitige Generierung; weitere Anfragen erhalten `429`. Ein anderes konfiguriertes Modell
im Request erhält `409`, bis es mit `use` geladen wurde. Kein automatischer Modellwechsel über HTTP.

Runtime: separat installiertes offizielles `sd-server master-987-a77d362`, inklusive eigener CUDA-13.4-
Laufzeitbibliotheken. Die vorhandenen Gewichte werden ausschließlich über absolute Pfade gelesen.
Ein kleiner Python-Standardbibliothek-Adapter ergänzt notwendige Validierung, Modellkennungen,
Authentifizierung und Ressourcenbegrenzung. Die native API alleine erfüllt diese Anforderungen nicht;
der [gemessene Nachweis und die Architekturentscheidung](docs/inspection.md) sind dokumentiert.

Dieses Repository enthält keine Modelle, Bilder oder anderen Binärassets. Vorhandene Bild- und
Spielverzeichnisse werden weder als Ausgabe verwendet noch bereinigt. Vorhandene `imgai`-Workflows
bleiben eigenständig; bei CLI-Nutzung den neuen Dienst vorher stoppen, um GPU-Konflikte zu vermeiden.

## Dokumentation

- [Installation, Updates, Deinstallation](docs/installation.md)
- [Konfiguration und Modellpfade](docs/configuration.md)
- [systemd und Ressourcen](docs/systemd.md)
- [API und Fehlercodes](docs/api.md)
- [Spätere Open-WebUI-Anbindung](docs/open-webui.md)
- [Fehlersuche](docs/troubleshooting.md)
- [Bestandsaufnahme und Runtime-Entscheidung](docs/inspection.md)
- [Prüfbericht](docs/test-report.md)

## Tests

```bash
cd ~/dev/github/local-image-ai-service
python3 -m unittest discover -s tests -v
# Verwendet die echte GPU, schaltet beide Modelle nacheinander und stoppt danach den Dienst:
python3 tests/integration.py
```

Python >=3.11, keine zusätzlichen Python-Pakete. Runtime-Revision und Prüfsummen stehen in
[runtime.lock.json](runtime.lock.json); die tatsächlich installierten Dateien zusätzlich in
`~/.local/share/local-image-ai-service/runtime/receipt.json`.
