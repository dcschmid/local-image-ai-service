# Prüfbericht — 28.10.2026

Getestet auf Fedora Linux 44 KDE, RTX 5070 Laptop 8 GB, NVIDIA 615.78.08, CUDA 13.4,
Python 3.14.8. Verwendet wurde ausschließlich der separat installierte offizielle Build
`master-987-a77d362`. Kein Neuaufbau oder Download von Modellen erforderlich.

## Automatisierte Tests

`python3 -m unittest discover -s tests -v`: **14 Testgruppen bestanden**, einschließlich 24
ungültiger Requestvarianten als Untertests. Abgedeckt: Modell-/Parameterprüfung, Größen, Seed,
private Dateirechte, Bearer-Key (richtig/falsch/fehlend), Origin-Sperre, Abwesenheit von Edit-/Chat-/
nativen Management-Routen, JSON-Fehler, sofortige 429-Antwort, begrenzte HTTP-Worker, fehlendes Modell,
Lade- und Generierungstimeout einschließlich tatsächlichem Beenden eigener Testprozesse.
Ein isolierter Installations-/Deinstallationstest mit simuliertem User-Manager prüft zusätzlich
Dateirechte, den Fedora-Timeout-Drop-in und den Erhalt fremder Modell-/Bild-/Projektverzeichnisse.
Diese Tests verwenden für Timeout-/HTTP-Fehler gezielt Test-Doubles; echte Inference ist separat geprüft.

`python3 tests/integration.py`: echte Modelle **nacheinander**, niemals parallele GPU-Benchmarks.

| Geforderte Prüfung | Ergebnis |
| --- | --- |
| Eigenes Repository / Installation | Bestanden; eigenes Git-Verzeichnis, private Konfiguration, Runtime-Prüfsummen |
| Erforderliche Modelldateien | Alle sieben lesbar |
| CUDA-/Backend-Healthcheck | CUDA0 mit RTX 5070, kein CPU-Fallback |
| systemd-Start und API erreichbar | Bestanden |
| `/v1/models` | Beide Kennungen, exakt ein geladenes Modell |
| MOSS-Bildgenerierung | 200, echtes 512×512-PNG, tatsächlicher Seed 42 |
| Z-Image-Bildgenerierung | 200, echtes 512×512-PNG, tatsächlicher Seed 42 |
| Modellwechsel | Alter Runtime-PID beendet, anschließend nur neues Modell bereit |
| Beenden / Neustarten | Alte Adapter-/Runtime-PIDs beendet, neue Runtime bereit |
| Stop während laufender Generierung | Bestanden; begrenzte Beendigungsdauer, eigene Runtime beendet |
| Ungültiges Modell | 404 `model_not_found` |
| Ungültige Bildgröße | 400 `invalid_size` |
| Anderes konfiguriertes Modell | 409 `model_not_loaded` |
| Mehrere Bilder | 400 `unsupported_n` bei n=2 |
| Paralleler Request während echter Inference | Sofortige 429-Antwort bei beiden Modellen |
| Nach Stop | Eigene PIDs verschwunden, Ports 7861/17861 geschlossen, keine eigenen GPU-Prozesse |
| Kein Login-Autostart | Unit `static`, kein Enable, keine automatischen Neustarts |

Alle Bildantworten wurden Base64-dekodiert, auf PNG-Signatur und korrekte Dimensionen geprüft,
sämtliche PNG-Chunk-CRCs validiert und die Pixeldaten erfolgreich dekomprimiert. Nichttrivialer
Bildinhalt und tatsächlicher Seed 42 wurden geprüft. Testbilder lagen nur in einem temporären
Unterordner von `~/.cache/local-image-ai-service` und wurden danach entfernt.

Abschließender vollständiger Durchlauf um 11:44 Uhr, 512×512, inklusive Inference und API-Antwort:

| Modell | Schritte / CFG | Dauer | PNG-Größe | SHA-256 |
| --- | --- | --- | --- | --- |
| moss | 20 / 3.0 | 21,20 s | 381.072 Bytes | `7cfb5e75d1a92fd41f7222c9d6e98e7bec021863dc6c0d467bf7ea0414566cfb` |
| z-image | 8 / 1.0 | 6,98 s | 365.149 Bytes | `f6176470009000b3176896436b94dff0ede5a42ab63fca7e557fac139560843c` |

Ein vorheriger vollständiger Durchlauf bestand ebenfalls (18,61 s / 7,88 s). MOSS war trotz gleichem
Seed nicht bitidentisch über die getrennten Prozesse; die API sagt keine deterministischen PNG-Hashes zu.

Zusätzlich: `systemd-analyze --user verify` ohne Fehler; Semgrep `p/python` mit 151 Regeln auf
den ausführbaren Python-Implementierungen ohne Befund. Der Prüfbericht behauptet keine visuelle
Qualitätsbewertung und keinen vollständigen Größen-/Prompt-Benchmark. Der optionale Quell-Neubau
und die spätere Open-WebUI-Anbindung wurden nicht ausgeführt.

## Integrität bestehender Dateien

Vor Implementierung wurde `scripts/audit.py` ausgeführt und erfasste **140.000 Einträge**, darunter
Dateiinhalte als SHA-256, Dateimodi, Änderungszeitstempel und Symlinkziele. Keine Änderung wird
automatisch zurückgesetzt. Baseline und Vergleich liegen ausschließlich im eigenen Cache.

| Geschützter Bereich | Baseline-Einträge | Ergebnis des ersten Abschlussvergleichs |
| --- | --- | --- |
| `~/.local/bin/imgai` | 1 | Unverändert, Inhalt/Modus/Zeitstempel |
| `~/dev/local-ai/image-stack` | 363 | Unverändert, einschließlich Character-, Kart-, Track-, Blueprint-, Reparatur- und Blender-Code sowie Git-Metadaten |
| `~/.local/share/local-image-ai` | 12.391 | Unverändert, einschließlich aller Gewichte, gemeinsam verwendeter Dateien, alter Runtime und venv |
| Alte `imgai-api.service` | 1 | Unverändert |
| `~/Pictures/AI-Generated` | 3.543 | Unverändert; 3.126 reguläre Dateien, einschließlich bestehender Bilder, Worlds und Benchmarks |
| `~/dev/github/riff-racers` | 123.685 | Während paralleler Arbeit Änderungen festgestellt; Details unten |
| `~/.local/share/riff-racers` | 3 | Unverändert |
| `~/.local/share/riff_racers` | 13 | Unverändert |

Der erste Vergleich ergab keine modifizierten oder entfernten Baseline-Dateien und acht neue
Scratch-Renderdateien. Ein zweiter, späterer Vergleich stellte weitere parallele Arbeit fest:
**33 neue Einträge, 10.572 modifizierte Einträge, keine entfernten Einträge**, sämtlich unter
`~/dev/github/riff-racers`. Die erneute Inhaltsprüfung der 10.572 modifizierten Einträge ergab
**18 abweichende SHA-256-Inhalte** und **10.554 Änderungen ausschließlich an Metadaten**.

Die 18 inhaltlichen Änderungen betreffen `.git/index`, zwei verarbeitete Rhythm-Kaur-/Dance-Fusion-
GLB-Dateien, zwei Scratch-Export-GLBs, die Scratch-Dateien `rhythm-kaur-work.blend` und `.blend1`,
sowie Defold-Buildartefakte und Build-/Versionsprotokolle. Neue Einträge sind Scratch-Renderings,
Capture-Logs und Verzeichnisse/Bilder unter `build/evidence/art-benchmark/rhythm-h1` und `rhythm-h2`.
Der vollständige Vergleich liegt lokal im Audit-Cache, die Zusammenfassung in `audit/summary.json`.

Zu den zuerst erkannten acht neuen Dateien gehörten:

```text
~/dev/github/riff-racers/build/scratch/rhythm-kaur/renders/
  cmp_s1_hero.png
  cmp_s1_ortho.png
  cmp_s1_top.png
  s1_back.png
  s1_front.png
  s1_hero.png
  s1_side.png
  s1_top.png
```

Diese Aufgabe hat keinen Schreibzugriff auf diese Pfade verwendet. Ein seit dem 23.10. laufender
Blender-Prozess war separat vorhanden. Die Herkunft der parallelen Änderungen wurde nicht abschließend
zugeordnet. Der neue systemd-Dienst hat `ProtectHome=read-only` mit Schreibfreigabe ausschließlich
für seinen eigenen Cache. Keine Datei wurde gelöscht, repariert oder zurückgesetzt.

Eine pauschale Aussage „das gesamte Riff-Racers-Verzeichnis hat sich während der Aufgabe nicht
verändert“ wäre deshalb falsch. Belegt ist: **CLI, bestehendes Image-AI-Quellprojekt inklusive
Workflows und Git-Metadaten, bisherige Runtime/venv, alle Modellgewichte und sämtliche vorhandenen
Dateien unter `~/Pictures/AI-Generated` blieben unverändert**. Für Riff Racers einschließlich seiner
Scratch-Blender-Dateien ist wegen paralleler Arbeit keine vollständige Unverändertheit belegbar.
Es gab durch diese Aufgabe keinen Eingriff in diese Dateien oder die andere laufende Arbeit.

## Lokale Belege und Reproduktion

```text
~/.cache/local-image-ai-service/audit/before.json
~/.cache/local-image-ai-service/audit/comparison.json
~/.cache/local-image-ai-service/audit/summary.json
~/.cache/local-image-ai-service/native-probe.json
~/.cache/local-image-ai-service/native-probe.log
~/.cache/local-image-ai-service/unit-tests.log
~/.cache/local-image-ai-service/integration-report.json
~/.cache/local-image-ai-service/integration-output.log
~/.cache/local-image-ai-service/semgrep-report.json
~/.local/share/local-image-ai-service/runtime/receipt.json
```

Der Integritätsvergleich liefert bei hinzugekommenen externen Dateien bewusst Exitcode 1 und
weist `added`, `modified` und `removed` getrennt aus. Das ist kein Grund, fremde Arbeit zu verändern.
Die vollständigen Manifeste werden nicht ins Repository übernommen.
