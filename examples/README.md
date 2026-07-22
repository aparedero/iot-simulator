# Example scenarios

This folder contains ready-to-run device configurations that showcase the
simulator's field generators, output protocols and payload encryption. Each file
is a self-contained JSON document:

```jsonc
{
  "name": "Human-readable title",
  "description": "What the scenario demonstrates",
  "sensors": [ /* one or more SensorConfig objects */ ]
}
```

The simulator discovers every `*.json` in this folder automatically — **drop a
new file here and it appears in the list** (no restart needed for the API; the
UI shows it the next time you open the Examples dialog).

## Three ways to load an example

### 1. From the web UI (easiest)

1. Open the app at <http://localhost:8000>.
2. Click **★ Examples** in the toolbar.
3. Pick a scenario and click **Load**.

The scenario's sensors are added to the current simulation and start streaming
immediately — watch them in the cards and the real-time log. Names are
auto-suffixed if they collide with existing sensors (e.g. `room-101-2`), so
loading is always non-destructive.

### 2. From the REST API

```bash
# List the available scenarios
curl http://localhost:8000/api/examples

# Load one (merge into the current simulation)
curl -X POST http://localhost:8000/api/examples/smart-building/import

# Load one, replacing everything already configured
curl -X POST "http://localhost:8000/api/examples/industrial-machine/import?replace=true"
```

### 3. By importing the file directly

Use the toolbar **⬆ Import** button and select the `.json` file, or:

```bash
curl -X POST "http://localhost:8000/api/config/import-raw?replace=false" \
  -H "Content-Type: text/plain" \
  --data-binary @examples/fleet-gps.json
```

> **Tip:** these files are also a good starting template. Export your own setup
> with **⬇ Export** (or `GET /api/config/export`), edit it, and re-import.

## The bundled scenarios

| File | Scenario | Highlights | Output |
|------|----------|------------|--------|
| [`smart-building.json`](smart-building.json) | Smart Building / BMS | `sine_wave` temperature, `gaussian_number` humidity, `random_walk` CO₂, occupancy, HVAC state; anomaly injection on | screen + **MQTT** |
| [`fleet-gps.json`](fleet-gps.json) | GPS Fleet Tracker | `geo_point` jittered around a depot, speed, heading, battery drain, trip state | screen + **HTTP webhook** |
| [`industrial-machine.json`](industrial-machine.json) | Predictive Maintenance | `sine_wave` RPM, `gaussian_number` vibration, `random_walk` bearing temp, weighted state enum; anomaly injection on | screen + **Kafka** |
| [`energy-meter.json`](energy-meter.json) | Smart Energy Meter | daily consumption curve, mains voltage/current, tariff band; **AES-256-GCM encrypted** | screen + **encrypted MQTT** |
| [`air-quality.json`](air-quality.json) | Air Quality Station | PM2.5/PM10 random walks, NO₂/O₃ gaussians, AQI category, fixed geo point | screen + **CoAP** |

### Notes on external dependencies

The **screen** output always works — you will see live data in the UI for every
scenario. The other outputs try to reach a real endpoint; if none is present the
target is tagged `<type>!ERR` in the log and the simulation keeps running. To see
them actually deliver:

- **MQTT** (`smart-building`) — subscribe to the public broker:
  ```bash
  mosquitto_sub -h broker.hivemq.com -t "iot/sim/building/#" -v
  ```
- **HTTP** (`fleet-gps`) — point `url` at any collector, or run a throwaway one:
  ```bash
  python -m http.server 9000        # then edit the example's url to /
  ```
- **Kafka** (`industrial-machine`) — needs a broker on `localhost:9092`.
- **CoAP** (`air-quality`) — needs a CoAP server on `localhost:5683`
  (e.g. `aiocoap-fileserver`).
- **Encrypted MQTT** (`energy-meter`) — set the key **before starting** the
  server so the sensor can encrypt:
  ```bash
  export METER_KEY=$(python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())")
  uvicorn app.main:app --port 8000
  ```
  A subscriber decrypts each envelope with the same `METER_KEY`
  (see [../docs/USAGE.md](../docs/USAGE.md#payload-encryption)).
