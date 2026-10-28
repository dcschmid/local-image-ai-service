# systemd-User-Service

Unit: `~/.config/systemd/user/local-image-ai.service`; kein Root-Daemon.
Anwendung: `~/.local/share/local-image-ai-service/app/`.
Arbeitsverzeichnis: `~/.cache/local-image-ai-service/work/`.

```bash
systemctl --user start local-image-ai
systemctl --user stop local-image-ai
systemctl --user restart local-image-ai
systemctl --user status local-image-ai
journalctl --user -u local-image-ai -f
```

`Type=simple` bedeutet, dass `systemctl start` vor abgeschlossener Modellinitialisierung zurückkehrt.
`local-image-ai-service start` wartet auf Bereitschaft und liefert bei Ladefehlern einen Fehlerstatus.
`/health` beschreibt den Zustand, `/ready` liefert bis zur Bereitschaft HTTP 503.
Ein geladener Dienst bleibt bis zum Stop aktiv; kein automatisches Idle-Unload.

## Prozess- und Ressourcenverhalten

Die Unit umfasst Adapter und genau einen eigenen `sd-server`. `KillMode=control-group` beendet die
gesamte Gruppe. Der Adapter sendet seinem Kind SIGTERM und wartet höchstens acht Sekunden, danach
SIGKILL mit höchstens fünf Sekunden Wartezeit. Die Unit erzwingt die Gesamtbeendigung spätestens nach
20 Sekunden. Ein eigener Drop-in `local-image-ai.service.d/20-bounded-stop.conf` setzt
`TimeoutStopFailureMode=kill`, um Fedoras generisches `abort` samt möglichem großen Core-Dump zu
überschreiben. Fremde Prozesse werden weder signalisiert noch beendet. Auch ein sofortiger Neustart
wartet über systemd auf die Bereinigung der vorherigen Gruppe.

`Restart=no`: kein automatischer Neustart bei Ladefehler, CUDA-Fehler oder OOM. Startbegrenzung:
höchstens zwei Starts pro 60 Sekunden. Bei bewusst schnellen Wartungszyklen gegebenenfalls:

```bash
systemctl --user reset-failed local-image-ai
local-image-ai-service start
```

Weitere Grenzen: `MemoryHigh=16G`, `MemoryMax=24G`, `MemorySwapMax=2G`, `CPUQuota=800%`,
`TasksMax=128`, `LimitNOFILE=256`, `OOMPolicy=stop`. Diese cgroup-Grenzen begrenzen RAM/CPU,
keinen dedizierten VRAM-Anteil. Der API-Adapter erlaubt eine Generierung ohne Warteschlange,
acht HTTP-Worker und einen Listen-Backlog von acht Verbindungen. Generationen über Kapazität
erhalten 429; vollständig belegte HTTP-Worker führen zu 503. Header/Body-Lese-Timeout: zehn Sekunden.

`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome=read-only`, `PrivateTmp`, `UMask=0077`
und eine Schreibfreigabe ausschließlich für den eigenen Cache schützen die bestehenden Dateien.
GPU-Geräte bleiben zugänglich; `PrivateDevices` wird deshalb nicht gesetzt.

Der Dienst führt beim Start einen konservativen Test auf fremde CUDA-Compute-Prozesse aus und
verweigert gegebenenfalls das Laden. KDEs vorhandener `kwin_wayland`- und Xwayland-Prozess werden
ausgenommen. Dieser Test verhindert keinen späteren parallelen CLI-Start. Keine gemeinsame Sperre
mit `imgai`: vor dessen Nutzung den Dienst stoppen und nachher bei Bedarf wieder starten.

## Kein Login-Autostart

Die Unit hat absichtlich keinen `[Install]`-Abschnitt und erscheint als `static`. Es wurde kein
`enable`, kein Linger und keine andere Autostart-Konfiguration gesetzt. Eine spätere bewusste
Entscheidung für Login-Autostart erfordert das Ergänzen eines geeigneten Install-Ziels.

Logs enthalten Modell-, Lade-, CUDA- und Fehlerzustände sowie HTTP-Statuscodes. Der Adapter protokolliert
keine Request-Bodies oder Schlüssel. Native Runtime-Meldungen und Metadaten können Prompts enthalten;
das User-Journal ist daher wie lokale Arbeitsdaten zu behandeln.
