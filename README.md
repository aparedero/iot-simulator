# IoT Device Simulator

[![Docker Hub](https://img.shields.io/docker/v/paredero/iot-simulator?label=docker%20hub&logo=docker&sort=semver)](https://hub.docker.com/r/paredero/iot-simulator)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/aparedero/iot-simulator/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)

![IoT Device Simulator UI](https://raw.githubusercontent.com/aparedero/iot-simulator/main/docs/image.png)

A configurable IoT device simulator with a real-time web UI. Define virtual
devices, generate realistic telemetry, and stream it to multiple targets —
screen, MQTT, Kafka, TCP/JSON, file, HTTP, AMQP and CoAP — with optional
payload encryption. The UI is available in English and Spanish.

## Features

- **Up to 100 devices**, each with its own interval and optional jitter.
- **Rich field generators:** timestamp, fixed/random number, **gaussian**,
  **random walk**, **sine wave**, fixed/random/pattern string, **boolean**,
  weighted **enum**, **UUID**, **geo-point** (GPS jitter) and file-driven values.
- **Multiple outputs per device**, combined freely: **screen, MQTT** (TLS/QoS/
  retain/auth), **Kafka, TCP/JSON, file, HTTP webhook, AMQP (RabbitMQ), CoAP**.
- **Optional AES-256-GCM payload encryption** per output.
- **Anomaly injection** to test alerting pipelines.
- **Bundled example scenarios** loadable in one click from the UI.
- **JSON / YAML import & export** of the full configuration.
- **Real-time WebSocket log**, dark/light themes.

## Quick start

### Docker

```bash
docker run --rm -p 8000:8000 paredero/iot-simulator:latest
# or, from a clone:
docker compose up
```

### Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open <http://localhost:8000>.

## Usage

1. Click **+ New sensor**, give it a name, add **fields** and **outputs**, and save.
2. Or click **★ Examples** to load a ready-made scenario (smart building, GPS
   fleet, industrial machine, energy meter, air quality).
3. Watch payloads stream live in the bottom log; start/stop, clone, edit or
   delete devices from their cards.
4. Use **Export / Import** to save and restore configurations (JSON or YAML).

The REST API and WebSocket are documented in-app via the **API** button, and at
`/docs` (Swagger UI).

## Configuration

Environment variables:

| Variable      | Default   | Description                                    |
|---------------|-----------|------------------------------------------------|
| `LISTEN_HOST` | `0.0.0.0` | Bind host for the TCP/JSON ingress listener.   |
| `LISTEN_PORT` | `5050`    | Port for the TCP/JSON listener (`0` disables). |
| `LOG_LEVEL`   | `INFO`    | Python logging level.                          |

Ports: `8000` (Web UI, REST API, WebSocket) and `5050` (TCP/JSON ingress).

## Documentation

| Guide | Description |
|-------|-------------|
| [docs/USAGE.md](https://github.com/aparedero/iot-simulator/blob/main/docs/USAGE.md) | User guide: fields, outputs, encryption, examples |
| [docs/API.md](https://github.com/aparedero/iot-simulator/blob/main/docs/API.md) | REST + WebSocket reference |
| [docs/CONFIG_SCHEMA.md](https://github.com/aparedero/iot-simulator/blob/main/docs/CONFIG_SCHEMA.md) | Sensor / field / output / encryption schema |
| [examples/](https://github.com/aparedero/iot-simulator/tree/main/examples) | Ready-to-import scenarios |

A Helm chart for Kubernetes is available in
[helm/iot-simulator/](https://github.com/aparedero/iot-simulator/tree/main/helm/iot-simulator).

## License

[MIT](https://github.com/aparedero/iot-simulator/blob/main/LICENSE) © 2026 IoT Device Simulator contributors.
