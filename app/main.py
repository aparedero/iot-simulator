"""FastAPI application: REST + WebSocket + static UI."""
from __future__ import annotations

import asyncio
import collections
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Deque, Dict, List, Set

import yaml
from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .models import ImportRequest, SensorConfig
from .publishers import PublisherHub
from .sensors import MAX_SENSORS, SensorManager

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("iot-sim")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
EXAMPLES_DIR = BASE_DIR.parent / "examples"

VERSION = "1.2.0"
START_TIME = time.time()


# ---------------------------------------------------------------------------
# WebSocket broadcaster + recent-events buffer
# ---------------------------------------------------------------------------

class EventBus:
    def __init__(self, buffer_size: int = 200) -> None:
        self.connections: Set[WebSocket] = set()
        self.buffer: Deque[Dict[str, Any]] = collections.deque(maxlen=buffer_size)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.connections.add(ws)
        for evt in list(self.buffer):
            try:
                await ws.send_json(evt)
            except Exception:
                break

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self.connections.discard(ws)

    async def publish(self, event: Dict[str, Any]) -> None:
        self.buffer.append(event)
        dead: List[WebSocket] = []
        for ws in list(self.connections):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self.connections.discard(ws)


bus = EventBus()
hub = PublisherHub()


async def _on_event(evt: Dict[str, Any]) -> None:
    await bus.publish(evt)


manager = SensorManager(hub, _on_event)


# ---------------------------------------------------------------------------
# Optional TCP listener: receive newline-JSON and rebroadcast on the bus
# ---------------------------------------------------------------------------

async def _handle_tcp_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer = writer.get_extra_info("peername")
    logger.info("TCP client connected: %s", peer)
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = {"raw": text}
            await bus.publish({
                "type": "ingress",
                "source": f"tcp:{peer[0]}:{peer[1]}" if peer else "tcp",
                "payload": payload,
            })
    except Exception as e:  # noqa: BLE001
        logger.warning("TCP client error: %s", e)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


_tcp_server: asyncio.base_events.Server | None = None


async def _start_tcp_listener(host: str, port: int) -> None:
    global _tcp_server
    _tcp_server = await asyncio.start_server(_handle_tcp_client, host, port)
    logger.info("TCP/JSON listener on %s:%s", host, port)


@asynccontextmanager
async def lifespan(app: FastAPI):
    listen_host = os.getenv("LISTEN_HOST", "0.0.0.0")
    listen_port = int(os.getenv("LISTEN_PORT", "5050"))
    if listen_port > 0:
        try:
            await _start_tcp_listener(listen_host, listen_port)
        except Exception as e:  # noqa: BLE001
            logger.error("TCP listener failed: %s", e)
    try:
        yield
    finally:
        await manager.shutdown()
        await hub.close()
        if _tcp_server is not None:
            _tcp_server.close()
            try:
                await _tcp_server.wait_closed()
            except Exception:
                pass


app = FastAPI(
    title="IoT Device Simulator",
    version=VERSION,
    description="A configurable IoT device simulator with MQTT/Kafka/TCP/JSON outputs.",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# UI / health / metrics
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "version": VERSION,
        "uptime_sec": int(time.time() - START_TIME),
        "sensors": len(manager.sensors),
        "max_sensors": MAX_SENSORS,
    }


@app.get("/api/metrics")
async def metrics() -> Dict[str, Any]:
    sensors = manager.list()
    return {
        "uptime_sec": int(time.time() - START_TIME),
        "total_messages": hub.total_messages,
        "total_errors": hub.total_errors,
        "sensors_total": len(sensors),
        "sensors_running": sum(1 for s in sensors if s.running),
        "max_sensors": MAX_SENSORS,
    }


@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def prometheus_metrics() -> PlainTextResponse:
    """Prometheus text exposition format for scraping/observability stacks."""
    sensors = manager.list()
    running = sum(1 for s in sensors if s.running)
    lines = [
        "# HELP iotsim_uptime_seconds Process uptime in seconds.",
        "# TYPE iotsim_uptime_seconds gauge",
        f"iotsim_uptime_seconds {int(time.time() - START_TIME)}",
        "# HELP iotsim_messages_total Total output messages dispatched.",
        "# TYPE iotsim_messages_total counter",
        f"iotsim_messages_total {hub.total_messages}",
        "# HELP iotsim_errors_total Total output errors.",
        "# TYPE iotsim_errors_total counter",
        f"iotsim_errors_total {hub.total_errors}",
        "# HELP iotsim_sensors Total configured sensors.",
        "# TYPE iotsim_sensors gauge",
        f"iotsim_sensors {len(sensors)}",
        "# HELP iotsim_sensors_running Currently running sensors.",
        "# TYPE iotsim_sensors_running gauge",
        f"iotsim_sensors_running {running}",
        "# HELP iotsim_sensor_messages_total Per-sensor messages sent.",
        "# TYPE iotsim_sensor_messages_total counter",
    ]
    for s in sensors:
        sid = s.id.replace('"', "")
        name = s.name.replace('"', "").replace("\\", "")
        lines.append(
            f'iotsim_sensor_messages_total{{sensor_id="{sid}",name="{name}"}} {s.messages_sent}'
        )
    return PlainTextResponse("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Sensor CRUD
# ---------------------------------------------------------------------------

@app.get("/api/sensors")
async def list_sensors() -> List[Dict[str, Any]]:
    return [s.model_dump() for s in manager.list()]


@app.post("/api/sensors", status_code=201)
async def create_sensor(cfg: SensorConfig) -> Dict[str, Any]:
    try:
        sensor = await manager.create(cfg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sensor.status().model_dump()


@app.get("/api/sensors/{sensor_id}")
async def get_sensor(sensor_id: str) -> Dict[str, Any]:
    if sensor_id not in manager.sensors:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return manager.sensors[sensor_id].status().model_dump()


@app.put("/api/sensors/{sensor_id}")
async def update_sensor(sensor_id: str, cfg: SensorConfig) -> Dict[str, Any]:
    try:
        sensor = await manager.update(sensor_id, cfg)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sensor not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sensor.status().model_dump()


@app.delete("/api/sensors/{sensor_id}", status_code=204, response_class=Response)
async def delete_sensor(sensor_id: str) -> Response:
    if sensor_id not in manager.sensors:
        raise HTTPException(status_code=404, detail="Sensor not found")
    await manager.delete(sensor_id)
    return Response(status_code=204)


@app.post("/api/sensors/{sensor_id}/start")
async def start_sensor(sensor_id: str) -> Dict[str, Any]:
    if sensor_id not in manager.sensors:
        raise HTTPException(status_code=404, detail="Sensor not found")
    await manager.start(sensor_id)
    return manager.sensors[sensor_id].status().model_dump()


@app.post("/api/sensors/{sensor_id}/stop")
async def stop_sensor(sensor_id: str) -> Dict[str, Any]:
    if sensor_id not in manager.sensors:
        raise HTTPException(status_code=404, detail="Sensor not found")
    await manager.stop(sensor_id)
    return manager.sensors[sensor_id].status().model_dump()


@app.post("/api/sensors/{sensor_id}/clone", status_code=201)
async def clone_sensor(sensor_id: str) -> Dict[str, Any]:
    try:
        new_sensor = await manager.clone(sensor_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sensor not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return new_sensor.status().model_dump()


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------

@app.post("/api/sensors/start-all")
async def start_all() -> Dict[str, Any]:
    n = await manager.start_all()
    return {"started": n, "total": len(manager.sensors)}


@app.post("/api/sensors/stop-all")
async def stop_all() -> Dict[str, Any]:
    n = await manager.stop_all()
    return {"stopped": n, "total": len(manager.sensors)}


@app.delete("/api/sensors")
async def delete_all() -> Dict[str, Any]:
    count = len(manager.sensors)
    await manager.shutdown()
    return {"deleted": count}


# ---------------------------------------------------------------------------
# Configuration import / export
# ---------------------------------------------------------------------------

@app.get("/api/config/export")
async def export_config(
    format: str = Query("json", pattern="^(json|yaml)$"),
) -> Response:
    payload = {
        "version": VERSION,
        "exported_at": int(time.time()),
        "sensors": [
            cfg_to_export(s) for s in (m.cfg for m in manager.sensors.values())
        ],
    }
    if format == "yaml":
        body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        headers = {"Content-Disposition": 'attachment; filename="iot-sim-config.yaml"'}
        return PlainTextResponse(body, media_type="application/x-yaml", headers=headers)
    headers = {"Content-Disposition": 'attachment; filename="iot-sim-config.json"'}
    return JSONResponse(content=payload, headers=headers)


def cfg_to_export(cfg: SensorConfig) -> Dict[str, Any]:
    data = cfg.model_dump(exclude_none=True)
    data.pop("id", None)
    return data


@app.post("/api/config/import")
async def import_config(req: ImportRequest) -> Dict[str, Any]:
    return await _do_import(req)


@app.post("/api/config/import-raw")
async def import_config_raw(
    request: Request,
    replace: bool = Query(False),
) -> Dict[str, Any]:
    """Import a raw JSON *or* YAML document (auto-detected).

    Accepts a full export document, a bare list of sensors, or ``{sensors: [...]}``.
    YAML is a superset of JSON, so ``yaml.safe_load`` parses both formats.
    """
    raw = (await request.body()).decode("utf-8", errors="replace")
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON/YAML: {e}")
    sensors = parsed if isinstance(parsed, list) else (parsed or {}).get("sensors")
    if not isinstance(sensors, list):
        raise HTTPException(status_code=400, detail="Expected a sensor list or {sensors: [...]}")
    try:
        req = ImportRequest(sensors=sensors, replace=replace)
    except Exception as e:  # noqa: BLE001 — surface validation errors as 400
        raise HTTPException(status_code=400, detail=str(e))
    return await _do_import(req)


async def _do_import(req: ImportRequest) -> Dict[str, Any]:
    try:
        if req.replace:
            created = await manager.replace_all(req.sensors)
        else:
            created = await manager.import_many(req.sensors)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"imported": len(created), "ids": [s.id for s in created]}


# ---------------------------------------------------------------------------
# Bundled example scenarios
# ---------------------------------------------------------------------------

@app.get("/api/examples")
async def list_examples() -> List[Dict[str, Any]]:
    """List the bundled example scenarios (name, description, sensor count)."""
    out: List[Dict[str, Any]] = []
    if not EXAMPLES_DIR.is_dir():
        return out
    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        out.append({
            "id": path.stem,
            "name": data.get("name", path.stem),
            "description": data.get("description", ""),
            "sensors": len(data.get("sensors", [])),
        })
    return out


@app.post("/api/examples/{example_id}/import")
async def import_example(example_id: str, replace: bool = Query(False)) -> Dict[str, Any]:
    """Load a bundled example scenario into the running simulator."""
    # Guard against path traversal — only accept a bare stem.
    if "/" in example_id or "\\" in example_id or ".." in example_id:
        raise HTTPException(status_code=400, detail="Invalid example id")
    path = EXAMPLES_DIR / f"{example_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Example not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    sensors = data.get("sensors", [])
    try:
        req = ImportRequest(sensors=sensors, replace=replace)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))
    return await _do_import(req)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await bus.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await bus.disconnect(ws)
