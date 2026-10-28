# HTTP-API

Basis: `http://127.0.0.1:7861/v1`, ausschließlich Bildgenerierung. JSON über HTTP, keine öffentliche
Freigabe, keine CORS-Freigabe. Requests mit `Origin` werden abgelehnt; Open WebUI ruft serverseitig auf.
Optionaler Bearer-Key gemäß [Konfiguration](configuration.md). Ohne Key keine Authentifizierung nötig.

## Endpunkte

| Methode | Pfad | Verhalten |
| --- | --- | --- |
| GET | `/v1/models` | OpenAI-Modellliste mit `moss`, `z-image`, `installed`, `loaded`, `capabilities` |
| POST | `/v1/images/generations` | Synchrone Generierung; genau ein Base64-PNG |
| GET | `/health` | 200 für lebenden Adapter; `status`, `active_model`, `backend_pid`, `error`, `busy` |
| GET | `/ready` | 200 bei geladenem Backend, sonst 503 |

`/v1/images/edits`, Chat-, Embedding-, Video-, SDAPI-, native Verwaltungs- und sonstige Endpunkte
sind am Service-Port nicht verfügbar (404). Die vorhandenen zwei Konfigurationen sind für Text-zu-Bild
geprüft. Eine native Route allein ist kein Nachweis geeigneter Modell-Editing-Unterstützung.

`/v1/models` bleibt auch bei einem Ladefehler erreichbar. `installed` prüft lesbare Dateien,
`loaded` tatsächliche Bereitschaft. Nur ein Eintrag kann `loaded: true` haben.

## Generierung

```bash
curl --fail-with-body http://127.0.0.1:7861/v1/images/generations \
  -H 'Content-Type: application/json' \
  -d '{"model":"moss","prompt":"A small red teapot on a white table","size":"512x512","n":1,"seed":42,"response_format":"b64_json"}'
```

Bei konfiguriertem Key zusätzlich `Authorization: Bearer <KEY>`. Antwort:

```json
{
  "created": 1793183935,
  "output_format": "png",
  "data": [{"b64_json": "<PNG as Base64>"}],
  "model": "moss",
  "seed": 42
}
```

`model` und `seed` in der Antwort sind lokale Erweiterungen. Die native PNG-Metadaten enthalten den
tatsächlich verwendeten Seed; dieser wurde in den Integrationstests geprüft. Gleicher Seed garantiert
keine bitidentischen Bilder über andere Runtime-/Hardwareversionen hinweg.

| Request-Feld | Behandlung |
| --- | --- |
| `model` | Optional; aktuell konfiguriertes Modell. Genau `moss` oder `z-image`. Anderes geladenes Modell: 409, unbekanntes Modell: 404 |
| `prompt` | Erforderlicher String, nicht leer, maximal 16.000 Zeichen |
| `seed` | Optionale lokale Erweiterung; Integer 0–2147483647, sonst zufällig erzeugt |
| `size` | Optional `768x768`; `WIDTHxHEIGHT`, je 256–1024 und Vielfache von 64, auch rechteckig |
| `n` | Optional; ausschließlich Integer 1, mehr Bilder nacheinander anfordern |
| `response_format` | Optional; ausschließlich `b64_json` |
| `output_format` | Optional; ausschließlich `png` |
| `user` | Optionaler String bis 256 Zeichen; als Kompatibilitätsmetadatum akzeptiert, nicht verwendet oder gespeichert |

Alle weiteren Parameter werden mit 400 abgelehnt, einschließlich `quality`, `style`, `steps`,
`cfg_scale`, `negative_prompt`, `background`, `output_compression` oder beliebiger Modellpfade.
Sampling ist modellabhängig fest konfiguriert, kein Parameter wird stillschweigend simuliert.
`sd_cpp_extra_args`- und LoRA-Steuer-Tags im Prompt werden abgelehnt. Der Adapter übersetzt ausschließlich
den validierten Seed in die dokumentierte native Erweiterung. Maximal 64 KiB Request-Body, JSON-Objekt,
`Content-Type: application/json`, genau ein `Content-Length`; kein Chunked-Request-Encoding.

## Fehler und Kapazität

```json
{"error":{"message":"Unknown model; choose moss or z-image","type":"invalid_request_error","code":"model_not_found","param":"model"}}
```

| HTTP | Code / Bedeutung |
| --- | --- |
| 400 | `invalid_size`, `invalid_seed`, `invalid_prompt`, `unsupported_parameter`, `unsupported_n` oder fehlerhaftes JSON |
| 401 | `invalid_api_key` |
| 403 | `origin_not_allowed` |
| 404 | `model_not_found` oder `not_found` |
| 409 | `model_not_loaded`; explizit `local-image-ai-service use MODELL` ausführen |
| 408 / 413 / 415 | HTTP-Lesefrist, Body-Limit oder falscher Content-Type |
| 429 | `generation_busy`, `Retry-After: 5`; keine Generierungswarteschlange |
| 502 | `backend_failed`; Runtime beendet, manueller Neustart nötig |
| 503 | `backend_not_ready`, `/ready` nicht bereit oder `server_busy` bei belegten HTTP-Workern |
| 504 | `generation_timeout`; eigene Runtime wird beendet, keine Hintergrundgenerierung |

Der Standard-Generierungstimeout beträgt 300 Sekunden bis zur Antwort des lokalen Backends;
nach Timeout benötigt die kontrollierte Prozessbereinigung bis zu weitere 13 Sekunden. Client-Timeout
mindestens 330 Sekunden wählen. Ein vorzeitiger Client-Abbruch garantiert keine Inference-Abbruchmeldung:
die bereits begonnene Generierung läuft höchstens bis zu ihrem Diensttimeout weiter und hält bis dahin
den einzelnen Generierungsplatz belegt. Fehler lösen keinen automatischen Retry oder Modell-Reload aus.

Es werden keine Ausgabe-URLs erzeugt und keine Bilder automatisch gespeichert. PNG und Antwort werden
im Arbeitsspeicher verarbeitet. Tests verwenden ausschließlich temporäre Ordner im eigenen Cache.
