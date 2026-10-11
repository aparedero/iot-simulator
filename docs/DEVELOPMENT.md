# Development Guide

## Project layout

```
iot-simulator/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI app, REST + WS, TCP/CoAP listeners, HTTP ingest
│   ├── settings.py        # Env + port standard
│   ├── paths.py           # Filesystem sandbox
│   ├── examples.py        # Example host rewrite for Compose labs
│   ├── models.py          # Pydantic schemas (fields, outputs, encryption)
│   ├── generators.py      # Field value generators
│   ├── crypto.py          # Optional AES-256-GCM payload encryption
│   ├── publishers.py      # Output sinks (screen/MQTT/Kafka/TCP/file/HTTP/AMQP/CoAP)
│   ├── sensors.py         # Sensor and SensorManager
│   └── static/            # UI (HTML + ES modules + CSS)
│       ├── index.html
│       ├── styles.css
│       ├── i18n.js
│       └── app.js
├── docs/                  # User & developer documentation
├── examples/              # Bundled importable scenarios (JSON)
├── sample_data/           # Sample files for the `file` field type
├── tests/                 # pytest suite
├── docker/                # Compose helper configs (Mosquitto)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt   # test dependencies
├── pytest.ini
├── LICENSE                # MIT
└── README.md
```

## Adding a new output protocol

1. Add an `<Xxx>Output` Pydantic model in `app/models.py` and include it in the
   `OutputConfig` union (add an `encryption: Optional[EncryptionConfig] = None`
   field if it is a transport output).
2. Add a pool/client class and an `isinstance` branch in
   `PublisherHub.dispatch` in `app/publishers.py`. Import the client library
   **lazily** inside the method so a missing optional dependency only degrades
   that one output.
3. Wire the UI: add entries to `OUTPUT_DEFAULTS`, `OUTPUT_SCHEMA` (and
   `ENCRYPTABLE`) in `app/static/app.js`, a button in `index.html`, and any
   new i18n keys.
4. Document it in `docs/CONFIG_SCHEMA.md` and add a test.

## Python matrix

| CPython | Status | End of life | Notes |
|---------|--------|-------------|-------|
| 3.15 | Supported | 2031-10 | CI. Official `python:3.15` Docker tag is not on Docker Hub yet (`3.15-rc` only). |
| 3.14 | Supported (Docker default) | 2030-10 | `python:3.14-alpine` runtime image. |
| 3.13 and older | Not supported | — | Dropped so the product stays on interpreters with a long support window. |

Runtime pins in `requirements.txt` are the latest stable releases that publish
wheels for both 3.14 and 3.15 (`pydantic` 2.14.1 is the first Pydantic that
declares 3.15). FastAPI 0.143.0 tests 3.14; its only 0.143 breaking change is
opt-in OpenTelemetry auto-setup, which this app does not use.

## Local development

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The UI is plain ES modules served from `/static/`; reload the browser to see
changes.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│  FastAPI (REST + WebSocket)                                │
│                                                            │
│  ┌─────────────┐    ┌────────────────┐   ┌──────────────┐  │
│  │ SensorMgr   │ →  │ Sensor (asyncio│ → │ PublisherHub │  │
│  │ (max 100)   │    │  task per dev) │   │ MQTT/Kafka/… │  │
│  └─────────────┘    └────────────────┘   └──────────────┘  │
│         │                   │                              │
│         ▼                   ▼                              │
│   /api/* REST          EventBus  ──► WebSocket /ws ──► UI  │
└────────────────────────────────────────────────────────────┘
            ▲
            │ newline-delimited JSON
       TCP listener (port 5050)
```

## Coding conventions

- Python 3.14 or 3.15, type hints everywhere.
- Pydantic for all I/O validation.
- Async I/O end-to-end (`asyncio` tasks per sensor; `aiokafka` for Kafka).
- Connection pooling for MQTT and Kafka (`MqttPool`, `KafkaPool`).
- No global mutable state outside the singleton `SensorManager` / `PublisherHub`.
- UI: plain ES modules and CSS variables — no build step required.

## Running the test suite

```bash
pip install -r requirements-dev.txt
make test          # or: pytest
```

The suite (`tests/`) covers:

- `test_generators.py` — every field generator (ranges, drift, bounds, file modes).
- `test_crypto.py` — AES-256-GCM round-trips, key sourcing, tamper detection.
- `test_publishers.py` — screen/file/HTTP dispatch, encryption, error isolation.
- `test_models.py` — Pydantic validation and the discriminated output union.
- `test_api.py` — full REST API via `TestClient`, JSON+YAML import/export,
  examples endpoints, path-traversal guard, and validation of every bundled example.
- `test_ui_contract.py` — static front-end guards (no browser needed): element
  ids referenced by `app.js` exist in `index.html`, `data-i18n` keys are
  translated, EN/ES dictionaries agree, and editor field/output types match the
  backend models.

The TCP and CoAP listeners are disabled in tests via `LISTEN_PORT=0` and
`COAP_LISTEN_PORT=0` (set in `tests/conftest.py`). `pytest.ini` adds the repo
root to `pythonpath` so both `pytest` and `python -m pytest` work.

## Continuous integration

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every push and
pull request:

1. **test** — installs `requirements-dev.txt`, byte-compiles `app/`, and runs
   `pytest` on Python 3.14 and 3.15.
2. **docker** — builds the image and smoke-tests `/api/health` and
   `/api/examples` inside the running container.

**TDD workflow:** write or adjust a test in `tests/` first, watch it fail
(`make test`), implement until it passes, then let CI confirm nothing else broke.

## Running smoke tests

Spin up the container and exercise the API:

```bash
curl -s localhost:8000/api/health
curl -s -X POST localhost:8000/api/sensors -H 'Content-Type: application/json' -d @docs/example-sensor.json
curl -s localhost:8000/api/sensors | jq
```

## Releasing a new version

1. Bump `VERSION` in `app/main.py` (and Helm `appVersion`, health tests).
2. Update `CHANGELOG.md` (when present).
3. Tag the commit and push.

## Contributing

Pull requests are welcome. Please:

- Keep changes focused; one feature per PR.
- Add or update documentation in `docs/`.
- Run `python -m compileall app` to ensure no syntax errors.
