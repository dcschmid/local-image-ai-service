# systemd user service

Unit: `~/.config/systemd/user/local-image-ai.service`; no root daemon.
Application: `~/.local/share/local-image-ai-service/app/`.
Working directory: `~/.cache/local-image-ai-service/work/`.

```bash
systemctl --user start local-image-ai
systemctl --user stop local-image-ai
systemctl --user restart local-image-ai
systemctl --user status local-image-ai
journalctl --user -u local-image-ai -f
```

With `Type=simple`, `systemctl start` returns before model initialization finishes.
`local-image-ai-service start` waits for readiness and returns an error on load failure.
`/health` describes the state; `/ready` returns 503 until ready. A loaded service remains
active until stopped; there is no automatic idle unloading.

## Processes and resources

The unit contains the adapter, exactly one owned `sd-server`, and a temporary CPU anatomy process
while checking a response. The CPU checker uses a separate session and exits after each check.
`KillMode=control-group`
terminates the entire group. The adapter sends its child SIGTERM and waits up to eight seconds,
then SIGKILL with up to five seconds to reap it. The unit enforces termination after 20 seconds.
Its own `local-image-ai.service.d/20-bounded-stop.conf` sets `TimeoutStopFailureMode=kill`
to override Fedora's generic `abort` setting and avoid a potentially large core dump.
Other processes are never signalled or killed. Restart waits for the previous group to be cleaned up.

`Restart=no` prevents automatic retries after load failures, CUDA failures, or OOM. The start limit
is two starts per 60 seconds. During deliberately rapid maintenance cycles, if necessary:

```bash
systemctl --user reset-failed local-image-ai
local-image-ai-service start
```

Additional limits: `MemoryHigh=20G`, `MemoryMax=28G`, `MemorySwapMax=2G`, `CPUQuota=800%`,
`TasksMax=128`, `LimitNOFILE=256`, and `OOMPolicy=stop`. These cgroup limits constrain RAM and
CPU, not a dedicated share of VRAM. The adapter admits one generation with no generation queue,
eight HTTP workers, and a listen backlog of eight connections. Excess generation requests receive
429; fully occupied HTTP workers cause 503. HTTP header/body read timeout: ten seconds.
The generation slot remains occupied during CPU screening. Its separate 180-second deadline
terminates only the checker; it does not discard a healthy GPU runtime. `LimitCORE=0` prevents
large dumps from native failures. The raised RAM limits accommodate the CPU vision model.

`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome=read-only`, `PrivateTmp`, `UMask=0077`,
and write access only to the service's own cache protect existing files. GPU devices remain
accessible; `PrivateDevices` is therefore not enabled. Optional CLI saving happens outside
the systemd process, so these restrictions remain unchanged.

At startup, the service conservatively checks for other CUDA compute processes and refuses to
load if any exist. The existing KDE `kwin_wayland` and Xwayland processes are excluded.
This check cannot prevent an existing CLI from starting later. There is no shared lock with
`imgai`: stop this service before using that CLI and start it again afterwards if needed.

## No login autostart

The unit deliberately has no `[Install]` section and is reported as `static`. No `enable`,
linger, or other autostart configuration has been set. A later explicit decision to enable
login autostart requires adding a suitable installation target.

Logs include model loading, CUDA state, errors, and HTTP status codes. The adapter does not
log request bodies or keys. Native runtime messages and metadata may contain prompts;
treat the user journal as local working data.
