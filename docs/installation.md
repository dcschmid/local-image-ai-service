# Installation und Wartung

## Voraussetzungen

Python >=3.11, systemd-User-Manager mit cgroup v2, NVIDIA-Treiber mit funktionierendem `nvidia-smi`.
Geprüft: Fedora 44 KDE, Python 3.14.8, NVIDIA 615.78.08, CUDA 13.4, RTX 5070 Laptop / SM 120,
64 GB RAM. Keine Root-Installation und keine System-Python-Pakete erforderlich.

Die Modellgewichte müssen bereits vorhanden sein. Die Installationsskripte laden keine Modelle herunter.
Etwa 690 MiB zusätzlicher Speicher werden für die unabhängige Runtime benötigt.

## Vorhandenen offiziellen Build separat installieren

```bash
cd ~/dev/github/local-image-ai-service
python3 scripts/install-runtime.py \
  --binary "$HOME/.local/share/local-image-ai/engines/sd-install/bin/sd-server" \
  --cuda-lib "$HOME/.local/share/local-image-ai/engines/cuda/lib" \
  --source "$HOME/.local/share/local-image-ai/engines/stable-diffusion.cpp"
python3 scripts/install.py
local-image-ai-service doctor
local-image-ai-service start
```

Das erste Skript prüft die gepinnte Quellrevision und die bekannte Binary-Prüfsumme. Es installiert
eigene Kopien des offiziellen Binaries sowie `libcudart.so.13`, `libcublas.so.13` und `libcublasLt.so.13`.
Es kopiert **keine Gewichte**. Alle Kopien werden per SHA-256 geprüft. Zur Laufzeit sind weder der
bisherige Quellcode noch dessen Binary, Python-Umgebung oder CUDA-Installationspfad erforderlich.
Die Systembibliotheken und der NVIDIA-Treiber bleiben Betriebssystemabhängigkeiten.

`install.py` installiert Anwendung, eigenen Launcher und Unit, erstellt bei Erstinstallation die
Konfiguration mit lokalen absoluten Pfaden und GPU-UUID. Eine vorhandene Konfiguration bleibt erhalten.
Es startet und aktiviert den Dienst nicht. `~/.local/bin` muss im `PATH` stehen.

## Eigener reproduzierbarer Quellbuild

Alternativ aus dem offiziellen Repository mit exakt gepinnter Revision und Submodulen bauen:

```bash
cd ~/dev/github/local-image-ai-service
local-image-ai-service stop
CUDA_TOOLKIT_ROOT="$HOME/.local/share/local-image-ai/engines/cuda" \
  bash scripts/build-runtime.sh
python3 scripts/install.py
local-image-ai-service doctor
local-image-ai-service start
```

Erfordert Git, CMake, Ninja, C/C++-Compiler und bestehendes CUDA-13.4-Toolkit. Das Toolkit wird nur
gelesen. Download und Build liegen ausschließlich unter `~/.cache/local-image-ai-service/build`.
Keine Verwendung des bisherigen stable-diffusion.cpp-Quellverzeichnisses. Die Buildkonfiguration ist
reproduzierbar; eine bitidentische Binary über unterschiedliche Compiler hinweg wird nicht zugesagt.
Der Neuaufbau ist ein Wartungsweg; für die Erstinstallation wurde der bekannte funktionierende
offizielle Build separat installiert und getestet.

## Updates

Anwendung aus diesem lokalen Repository erneut installieren:

```bash
cd ~/dev/github/local-image-ai-service
local-image-ai-service stop
python3 -m unittest discover -s tests -v
python3 scripts/install.py
local-image-ai-service start
```

Ein Runtime-Update erfolgt bewusst durch Änderung der Revision und Buildprüfung in einem eigenen
Änderungssatz, anschließend Build, Doctor und Integrationstests. Kein automatisches `git pull` einer
laufenden Runtime. `build-runtime.sh` baut den derzeit geprüften Pin erneut. Keine automatischen
Updates, Modell-Downloads oder Neustartschleifen.

## Deinstallation

```bash
cd ~/dev/github/local-image-ai-service
python3 scripts/uninstall.py
```

Entfernt ausschließlich diese User-Unit, diesen Launcher sowie die drei eigenen Verzeichnisse:

- `~/.local/share/local-image-ai-service`
- `~/.config/local-image-ai-service`
- `~/.cache/local-image-ai-service` einschließlich eigener Test-/Auditprotokolle

Repository, bestehende Installation `local-image-ai`, alle Modelle, Bilder und Spielprojekte bleiben
erhalten. Der Cache wird bei der Deinstallation entfernt; benötigte Auditprotokolle vorher sichern.
Keine Entfernung von `~/.local/share/local-image-ai` oder `~/Pictures/AI-Generated`.
