# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
semantic versioning.

## [1.2.0] — 2026-07-22

### Added

- **New output protocols**, reflecting current IoT communication trends:
  - **HTTP webhook** (`http`) — `POST`/`PUT` JSON to any endpoint, with custom
    headers, bearer or basic auth, configurable timeout and TLS verification.
    The dominant cloud-ingestion pattern (API Gateway, Event Grid, HTTP
    functions, Splunk HEC, generic collectors).
  - **AMQP 0-9-1** (`amqp`) — publish to RabbitMQ with a configurable exchange
    and routing key (supports the `{sensor}` placeholder).
  - **CoAP** (`coap`) — RFC 7252 over UDP, the classic protocol for
    constrained/low-power devices.
- **Optional AES-256-GCM payload encryption** on any transport output. Keys are
  supplied inline (`key_b64`) or, preferably, via an environment variable
  (`key_env`). Payloads are replaced with an authenticated envelope
  `{enc, iv, ct, tag, aad}`.
- **Seven new field generators** for realistic simulation: `gaussian_number`
  (noise), `random_walk` (drift), `sine_wave` (periodic cycles), `boolean`,
  weighted `enum`, `uuid`, and `geo_point` (GPS jitter within a radius).
- **YAML** configuration import/export (`GET /api/config/export?format=yaml`)
  and a raw JSON/YAML import endpoint (`POST /api/config/import-raw`).
- **Prometheus metrics** at `GET /metrics` (text exposition format), including
  per-sensor message counters.
- **Bundled example scenarios** (`examples/`) with `GET /api/examples` and
  `POST /api/examples/{id}/import`: smart building, GPS fleet tracker,
  industrial machine (predictive maintenance), smart energy meter (encrypted),
  and air-quality station.
- **UI**: buttons for all new field and output types, an inline 🔒 encryption
  section per output, and a **★ Examples** browser. English/Spanish throughout.
- **`pytest` test suite** (`tests/`, `requirements-dev.txt`, `pytest.ini`) plus
  a CI pipeline (`.github/workflows/ci.yml`) and `Makefile`.
- **Docker publishing** (`.github/workflows/docker-publish.yml`): builds a
  multi-arch image (`linux/amd64` + `linux/arm64`), pushes it to Docker Hub
  (`paredero/iot-simulator`) using repository secrets only, and syncs this
  README as the Docker Hub description.

### Security / hardening

- **Hardened `Dockerfile`**: multi-stage build (no compilers/pip cache in the
  runtime image), runs as a **non-root** user (`uid 10001`, `nologin`),
  read-only-root-filesystem friendly, `HEALTHCHECK` via the stdlib, OCI labels.
- **`python:3.12-alpine` base image** — eliminates the Debian OS-package CVEs
  (which had no upstream fix); the image scans clean of CRITICAL/HIGH
  vulnerabilities and is ~40% smaller.
- **Dependency upgrades** to clear known advisories: `cryptography` (→49.x),
  `python-multipart` (→0.0.3x), `fastapi`/`starlette` (patched Starlette) and
  `jinja2` (→3.1.6).
- **Expanded `.dockerignore`** so no secrets or dev artifacts can enter the
  build context.

### Changed

- Version bumped to `1.2.0`.
- Config export now omits `null` optional fields for cleaner output.
- `requirements.txt` adds `httpx`, `aio-pika`, `aiocoap`, `cryptography`,
  `PyYAML`. Protocol client libraries are imported lazily, so a missing optional
  dependency only degrades the affected output (tagged `<type>!ERR`) instead of
  breaking startup.

## [1.1.0] — initial public release

- FastAPI backend with REST + WebSocket, per-sensor asyncio tasks.
- Outputs: screen, MQTT (TLS/QoS/retain/auth), Kafka, TCP/JSON, file.
- Field generators: timestamp, fixed/random number, fixed/random string,
  pattern string, file-driven values.
- Anomaly injection, jitter, clone, bulk start/stop, JSON import/export.
- TCP/JSON ingress listener, real-time log UI, dark/light themes, EN/ES.
- Docker, docker-compose and Helm chart deployment.
