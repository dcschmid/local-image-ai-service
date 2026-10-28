# Vorbereitung für Open WebUI

Open WebUI wurde für diese Aufgabe weder installiert noch verändert. Die folgende Konfiguration ist
für eine spätere manuelle Einrichtung vorgesehen; die tatsächliche Integration wurde noch nicht getestet.

In **Admin → Settings → Images** einen OpenAI-kompatiblen Image-Generation-Backend auswählen:

| Einstellung | Wert |
| --- | --- |
| Engine | OpenAI / `openai` |
| Image API Base URL | `http://127.0.0.1:7861/v1` |
| Modell | `moss` (Standard) oder `z-image`, passend zum geladenen Dienstmodell |
| Größe | z.B. `512x512` oder `768x768` |
| Anzahl | 1 |
| API-Key | Konfigurierter Bearer-Key; ohne Dienst-Key bei Pflichtfeld ein Dummy wie `local-unused` |
| Ausgabe | Base64 / `b64_json` |

Image Editing deaktiviert lassen. Keine zusätzlichen `quality`-, `style`- oder anderen nicht
unterstützten Parameter senden. Falls die spätere Open-WebUI-Version solche Parameter grundsätzlich
sendet, wird die API sie ausdrücklich ablehnen; dann die Integration anhand dieser Version anpassen.
Es gibt keine OpenAI-Chat-Verbindung zu diesem Service.

Die entsprechenden dokumentierten Umgebungsvariablen lauten:

```text
ENABLE_IMAGE_GENERATION=true
IMAGE_GENERATION_ENGINE=openai
IMAGES_OPENAI_API_BASE_URL=http://127.0.0.1:7861/v1
IMAGE_GENERATION_MODEL=moss
IMAGE_SIZE=512x512
IMAGES_OPENAI_API_KEY=<configured-key-or-local-unused>
```

Die derzeitige Benennung stammt aus der [offiziellen Open-WebUI-Dokumentation](https://docs.openwebui.com/troubleshooting/image-generation/),
geprüft am 28.10.2026. Ein produktiver Open-WebUI-Test bleibt bewusst außerhalb dieses Auftrags.

Zuerst `local-image-ai-service use z-image` ausführen und Bereitschaft abwarten, danach das Modell in
Open WebUI auf `z-image` stellen. Nicht geladenes Modell: 409 mit `model_not_loaded`; kein automatischer
Wechsel. Der Dienst bedient immer nur eine Generierung, weitere Nutzer/Anfragen erhalten 429.

## Container-Netzwerk

In einem normalen Docker-Bridge-Container zeigt `127.0.0.1` auf den Container selbst. Ein auf dem Host
an `127.0.0.1` gebundener Dienst ist auch über `host.docker.internal`/`host-gateway` normalerweise
**nicht** erreichbar: dieser Name allein ändert die Bindeadresse des Dienstes nicht.

Für eine spätere Linux-Installation mit gemeinsamem Host-Netzwerk (`network_mode: host`) bleibt die
Base URL `http://127.0.0.1:7861/v1`. Host-Netzwerk ist auch in der
[offiziellen Docker-Anleitung](https://docs.docker.com/ai/model-runner/openwebui-integration/)
als Linux-Option beschrieben. Alternativ kann ein gezielt konfigurierter lokaler Tunnel zum
Adapter-Port verwendet werden; dies wäre eine separate bewusste Netzwerkkonfiguration.

Es wurden keine Container, Tunnel, Firewall-Regeln oder LAN-Freigaben angelegt. Der Dienst erlaubt
absichtlich nur Loopback. Ein API-Key allein macht ihn nicht über das Container-Gateway erreichbar.
