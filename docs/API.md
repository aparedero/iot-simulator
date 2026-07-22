# API Reference

Base URL: `http://<host>:8000`.

Interactive Swagger UI is available at `/docs` (provided by FastAPI).

---

## Health & metrics

### `GET /api/health`

```json
{
  "status": "ok",
  "version": "1.1.0",
  "uptime_sec": 124,
  "sensors": 3,
  "max_sensors": 100
}
```

### `GET /api/metrics`

```json
{
  "uptime_sec": 124,
  "total_messages": 4821,
  "total_errors": 0,
  "sensors_total": 3,
  "sensors_running": 2,
  "max_sensors": 100
}
```

### `GET /metrics`

Prometheus text exposition format for scraping / observability stacks:

```text
# HELP iotsim_messages_total Total output messages dispatched.
# TYPE iotsim_messages_total counter
iotsim_messages_total 4821
# TYPE iotsim_sensors_running gauge
iotsim_sensors_running 2
# TYPE iotsim_sensor_messages_total counter
iotsim_sensor_messages_total{sensor_id="a1b2c3d4",name="temp-01"} 512
```

Example Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: iot-simulator
    static_configs:
      - targets: ["iot-sim:8000"]
```

---

## Sensors

### `GET /api/sensors`

Returns a list of `SensorStatus` (see [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md)).

### `POST /api/sensors`

Create a sensor. Body: `SensorConfig`.

- **201 Created** with the new `SensorStatus`.
- **400 Bad Request** if the name is already used or the limit is reached.

### `PUT /api/sensors/{id}`

Replace the configuration of a sensor. The sensor keeps its `id`. If it was
running it is restarted with the new configuration.

### `DELETE /api/sensors/{id}`

Stop and delete the sensor.

### `POST /api/sensors/{id}/start`
### `POST /api/sensors/{id}/stop`

Lifecycle controls.

### `POST /api/sensors/{id}/clone`

Create a deep copy of the sensor with an auto-generated unique name
(`<name>-copy`, `<name>-copy-2`, …). The clone is created **stopped**.

---

## Bulk

### `POST /api/sensors/start-all`
### `POST /api/sensors/stop-all`

Returns `{ "started": N, "total": T }` or `{ "stopped": N, "total": T }`.

### `DELETE /api/sensors`

Stops and removes **all** sensors.

---

## Configuration import / export

### `GET /api/config/export`

Streams `iot-sim-config.json`. Pass `?format=yaml` to download `iot-sim-config.yaml`
instead.

```json
{
  "version": "1.2.0",
  "exported_at": 1745000000,
  "sensors": [ { /* SensorConfig (without id) */ } ]
}
```

### `POST /api/config/import`

Body:

```json
{
  "sensors": [ { /* SensorConfig */ } ],
  "replace": false
}
```

- `replace=false` (default) — keep existing sensors; auto-suffix conflicting names.
- `replace=true` — delete all current sensors first.

Returns `{ "imported": N, "ids": ["..."] }`.

### `POST /api/config/import-raw?replace=false`

Import a **raw JSON or YAML** document (auto-detected — YAML is a JSON superset).
Send the file contents as the request body with `Content-Type: text/plain`.
Accepts a full export document, a bare sensor list, or `{ "sensors": [...] }`.

```bash
curl -X POST "http://localhost:8000/api/config/import-raw?replace=true" \
  -H "Content-Type: text/plain" --data-binary @config.yaml
```

---

## Example scenarios

### `GET /api/examples`

Lists the bundled scenarios:

```json
[ { "id": "smart-building", "name": "Smart Building", "description": "…", "sensors": 1 } ]
```

### `POST /api/examples/{id}/import?replace=false`

Loads a bundled scenario into the running simulator. `replace=true` wipes
existing sensors first. Returns `{ "imported": N, "ids": ["..."] }`.

```bash
curl -X POST http://localhost:8000/api/examples/industrial-machine/import
```

---

## WebSocket

### `WS /ws`

The server pushes JSON events. Possible shapes:

| Type | Fields |
|------|--------|
| `sample`  | `sensor_id`, `sensor_name`, `payload`, `targets[]`, `count`, `errors` |
| `created` | `sensor_id`, `sensor_name` |
| `updated` | `sensor_id`, `sensor_name` |
| `deleted` | `sensor_id`, `sensor_name` |
| `error`   | `sensor_id`, `sensor_name`, `message` |
| `ingress` | `source` (e.g. `tcp:1.2.3.4:5050`), `payload` |

When a client connects, the last 200 events are replayed.
