# Usage Guide

## Web UI

Open <http://localhost:8000>.

### Top bar

- **Running counter** and **total messages** metrics.
- **WebSocket status** indicator.
- **Language switcher** (EN / ES).
- **Theme toggle** (dark / light).

### Toolbar

| Button | Action |
|--------|--------|
| **+ New sensor** | Open the sensor editor. |
| **★ Examples** | Browse and load bundled industry scenarios. |
| **▶ Start all** | Start every defined sensor that is currently stopped. |
| **■ Stop all** | Stop every running sensor. |
| **⬇ Export** | Download the current configuration as `iot-sim-config.json` (YAML via the API: `?format=yaml`). |
| **⬆ Import** | Load a JSON **or** YAML file. You will be asked whether to *replace* existing sensors. |
| **↻ Reload** | Refresh sensor list from the backend. |
| **Search** | Filter sensors by name or id. |

### Sensor card

Each card shows:

- Name, id, interval, message count and (in red) error count.
- Status pill (running / stopped).
- The latest payload pretty-printed.
- The last successful targets (`screen`, `mqtt(host:port/topic)`, …).
- Actions: **Start / Stop**, **Edit**, **Clone**, **Delete**.

### Sensor editor

Compact modal with three sections:

1. **Basics** — name (must be unique), interval, jitter, "start on save".
2. **Anomaly injection** — enable, probability, factor range. When enabled,
   numeric fields may be spiked or dropped to simulate anomalies.
3. **Fields** and **Outputs** — add as many as you want; each block is
   removable individually.

### Real-time log

Bottom panel streamed via WebSocket. Use the dropdown to filter by
`samples`, `ingress`, `errors` or lifecycle `events`. Toggle autoscroll on/off
and clear at any time.

---

## Field types

| Type             | Properties                                  | Example value          |
|------------------|---------------------------------------------|------------------------|
| `timestamp`      | `fmt`: `iso` \| `epoch_ms` \| `epoch_s`     | `2026-04-30T12:00:00Z` |
| `fixed_number`   | `value`                                     | `42`                   |
| `random_number`  | `min`, `max`, `decimals`                    | `21.42`                |
| `fixed_string`   | `value`                                     | `"online"`             |
| `random_string`  | `length`, `charset`                         | `"a8FzK0pQ"`           |
| `pattern_string` | `pattern` with tokens (see below)           | `"DEV-1234-7"`         |
| `file`           | `path`, `mode` (`loop` / `sequential` / `random`) | line from file   |
| `gaussian_number`| `mean`, `stddev`, `decimals`, `min?`, `max?`| `20.13` (noisy)        |
| `random_walk`    | `start`, `step`, `min`, `max`, `decimals`   | drifts: `50.2, 50.9, …`|
| `sine_wave`      | `amplitude`, `offset`, `period_sec`, `phase`, `noise`, `decimals` | daily cycle |
| `boolean`        | `p_true`                                    | `true` / `false`       |
| `enum`           | `values[]`, `weights[]?`                    | `"warn"`               |
| `uuid`           | —                                           | `"9991ecb2-…"`         |
| `geo_point`      | `lat`, `lon`, `radius_m`, `decimals`        | `{"lat":40.4,"lon":-3.7}` |

> **Choosing a numeric generator:** use `random_number` for independent draws,
> `gaussian_number` for realistic noise around a setpoint, `random_walk` for
> slow-moving quantities (temperature, battery, level), and `sine_wave` for
> predictable periodic signals (daily temperature or energy demand).

### Pattern tokens

| Token              | Meaning                                  |
|--------------------|------------------------------------------|
| `{d:N}`            | `N` random digits                        |
| `{a:N}`            | `N` random letters                       |
| `{h:N}`            | `N` hex chars                            |
| `{choice:a|b|c}`   | One literal at random from the list      |
| `{seq}`            | Per-field incremental counter (1, 2, …)  |

Example: `DEV-{d:4}-{choice:north|south|east|west}-{seq}` →
`DEV-7521-east-42`.

---

## Outputs

| Output | Notes |
|--------|-------|
| **screen** | Always shows in the UI log. |
| **mqtt** | `host`, `port`, `topic` (with `{sensor}` placeholder), `qos`, `retain`, `tls`, optional auth. |
| **kafka** | `bootstrap_servers`, `topic`, optional `key_field` (uses that payload field as the message key). |
| **tcp_json** | Sends newline-delimited JSON to `host:port`. |
| **file_output** | Appends/overwrites a local file (`jsonl` or `json_pretty`). |
| **http** | HTTP webhook — `POST`/`PUT` JSON to a `url`, custom `headers`, bearer/basic auth, `verify_tls`. |
| **amqp** | Publishes to an AMQP 0-9-1 broker (RabbitMQ): `url`, `exchange`, `routing_key` (with `{sensor}`). |
| **coap** | Sends to a CoAP server (RFC 7252) over UDP: `uri`, `method`. |

Outputs can be combined freely in the same sensor. A failing output is tagged
`<type>!ERR` in the log and does **not** stop the others.

## Payload encryption

Every transport output (all except `screen`) can optionally encrypt its payload
with **AES-256-GCM** before sending. Enable it in the output block of the editor
(the 🔒 section) or in the config:

```jsonc
{ "type": "mqtt", "host": "...", "topic": "iot/sim/{sensor}",
  "encryption": { "enabled": true, "algorithm": "AES-256-GCM", "key_env": "METER_KEY" } }
```

Provide the 256-bit key either inline (`key_b64`) or, preferably, via an
environment variable (`key_env`) so secrets never end up in exported configs.
Generate a key:

```bash
python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
export METER_KEY="<paste-the-key>"
```

Consumers receive an envelope `{"enc","iv","ct","tag","aad"}` and decrypt it with
the same key. See [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md#encryptionconfig-optional-per-output).

## Example scenarios

The simulator ships with five ready-to-run industry scenarios:

| Example | What it shows |
|---------|---------------|
| **Smart Building** | Daily-cycle temperature, drifting humidity/CO₂, occupancy → MQTT |
| **GPS Fleet Tracker** | Jittered GPS, speed/heading, battery drain → HTTP webhook |
| **Industrial Machine** | RPM/vibration/bearing-temp with anomaly injection → Kafka |
| **Smart Energy Meter** | Consumption curve, mains voltage → **encrypted** MQTT |
| **Air Quality Station** | PM2.5/PM10/NO₂/O₃ + AQI category → CoAP |

### Load one from the web UI

1. Click **★ Examples** in the toolbar.
2. Browse the list — each card shows a description and sensor count.
3. Click **Load**. The sensors are added to the current simulation and start
   streaming right away (you'll see them appear as cards and in the log).

Loading is **non-destructive**: conflicting names are auto-suffixed, so you can
combine several scenarios. To start from a blank slate first, use **■ Stop all**
/ delete, or import with `replace=true` via the API.

### Load one from the API

```bash
curl http://localhost:8000/api/examples                              # list
curl -X POST http://localhost:8000/api/examples/smart-building/import  # load (merge)
curl -X POST "http://localhost:8000/api/examples/air-quality/import?replace=true"  # replace all
```

Full details, per-scenario notes, and how to see each output actually deliver
(MQTT/HTTP/Kafka/CoAP/encrypted) are in
[`examples/README.md`](../examples/README.md).

---

## Import / Export

`Export` produces a JSON document like:

```json
{
  "version": "1.1.0",
  "exported_at": 1745000000,
  "sensors": [ { /* SensorConfig */ } ]
}
```

`Import` accepts either that document, a bare list of sensors, or a
`{ "sensors": [...] }` payload. When importing without "replace", names that
collide are auto-suffixed (`temp`, `temp-2`, `temp-3`, …).
