# Bestandsaufnahme und Architekturentscheidung, 28.10.2026

## Bestehende Installation: ausschließlich gelesen

- CLI: `~/.local/bin/imgai`, 188-Byte-Shell-Launcher für die bestehende venv.
- Quellprojekt: `~/dev/local-ai/image-stack`.
- Inference-Binaries: `~/.local/share/local-image-ai/engines/sd-install/bin/{sd-cli,sd-server}`.
- Version: `master-987-a77d362`, vollständige Revision `a77d3623180b2bc1886f3dd04c0aa04156a987ef`.
- Offizieller stable-diffusion.cpp-Quellbaum war an dieser Revision unverändert.
- Rootless CUDA-Toolkit: `~/.local/share/local-image-ai/engines/cuda`, Version 13.4.92.
- Build: Release, `SD_CUDA=ON`, `CMAKE_CUDA_ARCHITECTURES=120`, CUDA-Flag `-allow-unsupported-compiler`.
- GPU: RTX 5070 **Laptop** GPU, 8151 MiB laut Treiber, Compute Capability 12.0; NVIDIA 615.78.08.
- Referenzparameter aus bestehendem `registry.py`, `build-engine.sh` und dokumentierten Benchmarks:
  CPU-Offloading, Flash Attention, Euler; MOSS 20 Schritte/CFG 3, Z-Image 8 Schritte/CFG 1.
- Sieben benötigte Modelldateien vorhanden; konkrete Rollen und Namen in [configuration.md](configuration.md).
- `sd-server --list-devices` meldet CUDA0. Ohne passenden Library-Pfad fehlt `libcudart.so.13`.
- Alte API-Unit `imgai-api.service` existiert, war inaktiv; ebenfalls Port 7861. Sie wurde nicht geändert.

Die alten Image-AI- und Riff-Racers-Repositories enthielten bereits uncommittete Änderungen.
Sie wurden weder bereinigt noch committet. Das Audit erfasst deshalb tatsächliche Dateiinhalte,
Dateimodi, Dateizeitstempel, Symlinkziele und auch bestehende Git-Metadaten statt nur `git diff`.

## Native API tatsächlich geprüft

Quelle: offizieller [OpenAI-Routencode der gepinnten Revision](https://github.com/leejet/stable-diffusion.cpp/blob/a77d3623180b2bc1886f3dd04c0aa04156a987ef/examples/server/routes_openai.cpp)
und [zugehörige API-Dokumentation](https://github.com/leejet/stable-diffusion.cpp/blob/a77d3623180b2bc1886f3dd04c0aa04156a987ef/examples/server/api.md).

Die Quellenprüfung ergab native Generation-, Edit- und Model-Routen. Ein kontrollierter echter
MOSS-Probelauf des separat installierten Binaries bestätigte:

| Prüfung | Ergebnis |
| --- | --- |
| `GET /v1/models` | 200, einziges ID `sd-cpp-local` |
| `POST /v1/images/generations` mit `model=does-not-exist` und `size=invalid-size` | **200 und Bild erzeugt**, unbekannte Modellkennung ignoriert, ungültige Größe auf CLI-Default zurückgefallen |
| `POST /v1/images/edits` ohne Bild | 400; vorhandene Route, kein Nachweis eines brauchbaren Editing-Modells |

Native Generierung unterstützt `prompt`, `n`, Größe und Base64-Ausgabe. Der lokale Seed muss bei
diesem Pin über `<sd_cpp_extra_args>` transportiert werden; ein top-level `seed` wird nicht gelesen.
Natives `/v1/models` bildet die gewünschten Kennungen nicht ab. Der Quellcode bestätigt außerdem,
dass unbekannte top-level-Felder nicht strikt abgelehnt werden. Native Modellverwaltung über
`/sdcpp/v1/models/*` ist vorhanden; sie wird von dieser Anwendung nicht exponiert oder verwendet.

## Warum ein kleiner Adapter notwendig ist

Native Modellkennung/-validierung und Ressourcen-/Parameterregeln erfüllen die verbindlichen
Anforderungen nicht. Deshalb ein eigenständiger Adapter aus Python-Standardbibliothek, ohne FastAPI,
ohne Pakete und ohne Übernahme von Modulen aus dem bisherigen Projekt. Er übernimmt ausschließlich
HTTP-Validierung, Modell-Metadaten, optionale Authentifizierung, eine nicht wartende Generierungssperre,
Prozessbereitschaft/-beendigung und Timeouts. Die Inference bleibt vollständig im offiziellen Binary.

Es wird pro Service-Start genau ein Modell geladen. Wechsel erfolgen durch Stop/Start der eigenen
Unit; dadurch bleiben das 8-GB-Limit und die Prozessbesitzverhältnisse einfach nachprüfbar.
Kein dynamisches Modellladen über einen beliebigen HTTP-Request und keine Freigabe der umfangreichen
nativen Verwaltungs-, Video-, WebUI- oder Dateipfad-APIs am öffentlichen Service-Port.

## Getrennte Runtime

Der bekannte offizielle Build wurde mit SHA-256-Prüfung separat unter
`~/.local/share/local-image-ai-service/runtime` installiert. CUDA-Laufzeitbibliotheken sind ebenfalls
eigene reguläre Dateien, keine Links in das alte Projekt. Eigenes gepinntes Buildskript liegt bei.
Es gibt keine Laufzeitabhängigkeit vom alten Quellcode oder dessen venv. Ausschließlich die bereits
vorhandenen Gewichte werden weiterhin über ihre absoluten Pfade gelesen.

Keine bestehenden Programme wurden auf die neue API umgestellt. Keine Open-WebUI-, Firewall-,
Blender-, Defold- oder Projektkonfiguration wurde geändert.
