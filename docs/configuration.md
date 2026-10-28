# Konfiguration

Aktive Datei: `~/.config/local-image-ai-service/config.json`, Eigentümer aktueller Benutzer,
Modus `0600`. Vorlage: [config.example.json](../config/config.example.json).
Konfiguration und API-Key gehören nicht ins Git-Repository. Änderungen werden beim Neustart gelesen.

| Feld | Standard / Bedeutung |
| --- | --- |
| `active_model` | `moss`; ausschließlich `moss` oder `z-image` |
| `host` | Nur `127.0.0.1` zulässig |
| `port` | 7861, öffentliche lokale API |
| `backend_port` | 17861, ausschließlich lokale interne Runtime |
| `runtime` | Absoluter Pfad des eigenen `runtime/bin/sd-server` |
| `cuda_lib` | Absoluter Pfad der eigenen CUDA-Laufzeitbibliotheken |
| `gpu_uuid` | Von `nvidia-smi` ermittelte GPU-UUID |
| `load_timeout` | 180 Sekunden; zulässig 1–1800 |
| `generation_timeout` | 300 Sekunden; zulässig 1–1800 |
| `api_key_file` | `null` oder absoluter Pfad einer privaten Schlüsseldatei |
| `models` | Genau zwei Einträge mit absoluten lesbaren Dateipfaden |

## Bereits vorhandene Gewichte

Wurzel auf diesem Rechner: `~/.local/share/local-image-ai/models/`. Die installierte JSON-Datei
enthält expandierte absolute Pfade; `~`, Umgebungsvariablen und relative Pfade werden nicht expandiert.

| Modell | Rolle | Datei unter Modellwurzel |
| --- | --- | --- |
| moss | diffusion | `moss/MOSS-Image-SFT-Q4_K.gguf` |
| moss | llm | `moss/Qwen3.5-9B-Q4_K_M.gguf` |
| moss | vae | `moss/flux2-vae.safetensors` |
| moss | tokenizer | `moss/tokenizer_qwen3.5.json` |
| z-image | diffusion | `z-image/z_image_turbo-Q4_K.gguf` |
| z-image | llm | `z-image/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| z-image | vae | `z-image/flux1-ae.safetensors` |

`llm` bezeichnet hier ausschließlich den Textencoder für Bildgenerierung. Es wird keine Chat-API
bereitgestellt. Gemeinsame Encoder können über identische absolute Pfade referenziert werden;
keine Datei wird kopiert, verändert oder vom Service gelöscht.

## Modellwechsel

```bash
local-image-ai-service use z-image
local-image-ai-service use moss
```

`use` prüft zunächst die benötigten Dateien, stoppt dann die eigene vollständige systemd-Prozessgruppe,
schreibt atomar die private Konfiguration und startet neu. Maximal ein Modell ist geladen. Der Befehl
wartet auf Bereitschaft. Laufende Anfragen werden beim Wechsel abgebrochen. Es gibt keinen HTTP-
Modellwechsel und keinen Eingriff in `imgai` oder dessen Konfiguration.

Fehlende Dateien vor dem Wechsel lassen den aktuellen Dienst unangetastet. Ein späterer Ladefehler
führt zu `/ready` = 503 und manueller Fehlerbehebung; kein automatisches Zurückschalten oder Reload.

## Sampling und Speicher

MOSS: Euler, 20 Schritte, CFG 3.0. Z-Image: Euler, 8 Schritte, CFG 1.0.
Standardgröße 768×768; API-Grenzen siehe [API](api.md). Beide mit `--offload-to-cpu`,
`--flash-attn on`, explizitem `--backend cuda0`, VAE-Tiling, acht CPU-Threads und einem
Conditioning-Cache-Eintrag. Diese Begrenzungen gelten nur für den neuen Dienst.

CUDA-Bibliotheken stammen ausschließlich aus dessen eigener Runtime. GPU-Auswahl erfolgt über
`CUDA_VISIBLE_DEVICES`; ein nicht verfügbarer CUDA-Backend führt zum Fehler statt CPU-Fallback.
Keine harte VRAM-Partitionierung: parallele fremde GPU-Nutzung kann weiterhin OOM verursachen.

## Optionaler Bearer-Key

Eine private Schlüsseldatei erzeugen, ohne den Wert auszugeben:

```bash
python3 - <<'PY'
from pathlib import Path
import os, secrets
os.umask(0o077)
p = Path.home() / '.config/local-image-ai-service/bearer-key'
with p.open('x') as stream:
    stream.write(secrets.token_urlsafe(32) + '\n')
p.chmod(0o600)
PY
```

`api_key_file` in der JSON-Konfiguration auf den absoluten Pfad setzen, dann Dienst neu starten.
Mindestens 24 Zeichen, Eigentümer aktueller Benutzer und Modus `0600` werden geprüft. Danach ist
für **alle vier öffentlichen Endpunkte** `Authorization: Bearer <KEY>` erforderlich. Ohne Schlüssel
ist kein Header nötig; ein Client-Dummy-Key wird dann ignoriert. Schlüsseländerungen benötigen Neustart.

Die interne native Runtime bleibt auf Loopback ohne Authentifizierung. Der Key schützt den Adapter,
stellt aber keine Sicherheitsgrenze gegenüber anderen lokalen Benutzern dar. Ein späterer lokaler
Tunnel darf nur den Adapter-Port weiterleiten. Der Dienst selbst akzeptiert keine LAN-Bindeadresse.
