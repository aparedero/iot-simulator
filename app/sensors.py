"""Sensor lifecycle management."""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .generators import SensorState, build_payload
from .models import SensorConfig, SensorStatus
from .publishers import PublisherHub

logger = logging.getLogger(__name__)

MAX_SENSORS = 100


class Sensor:
    def __init__(
        self,
        cfg: SensorConfig,
        hub: PublisherHub,
        on_event: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        if not cfg.id:
            cfg.id = uuid.uuid4().hex[:8]
        self.cfg = cfg
        self.hub = hub
        self.on_event = on_event
        self.state = SensorState()
        self._task: Optional[asyncio.Task] = None
        self.messages_sent = 0
        self.errors = 0
        self.last_payload: Optional[Dict[str, Any]] = None
        self.last_error: Optional[str] = None
        self.last_targets: List[str] = []

    @property
    def id(self) -> str:
        return self.cfg.id  # type: ignore[return-value]

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def _maybe_inject_anomaly(self, payload: Dict[str, Any]) -> bool:
        a = self.cfg.anomaly
        if not a.enabled or a.probability <= 0:
            return False
        if random.random() >= a.probability:
            return False
        numeric_keys = [k for k, v in payload.items() if isinstance(v, (int, float))]
        if not numeric_keys:
            return False
        key = random.choice(numeric_keys)
        factor = random.uniform(a.min_factor, a.max_factor)
        # 50/50 sign flip to allow downward spikes
        if random.random() < 0.5:
            factor = 1.0 / factor if factor != 0 else factor
        payload[key] = round(payload[key] * factor, 4)
        payload["_anomaly"] = {"field": key, "factor": round(factor, 4)}
        return True

    async def start(self) -> None:
        if self.running:
            return
        self.cfg.running = True
        self._task = asyncio.create_task(self._run(), name=f"sensor-{self.id}")

    async def stop(self) -> None:
        self.cfg.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _run(self) -> None:
        try:
            while self.cfg.running:
                payload = build_payload(self.cfg.fields, self.state)
                self._maybe_inject_anomaly(payload)
                try:
                    targets = await self.hub.dispatch(self.cfg.name, self.cfg.outputs, payload)
                    self.last_error = None
                except Exception as e:  # noqa: BLE001
                    self.errors += 1
                    self.last_error = str(e)
                    targets = [f"error:{e.__class__.__name__}"]
                self.messages_sent += 1
                self.last_payload = payload
                self.last_targets = targets
                await self.on_event({
                    "type": "sample",
                    "sensor_id": self.id,
                    "sensor_name": self.cfg.name,
                    "payload": payload,
                    "targets": targets,
                    "count": self.messages_sent,
                    "errors": self.errors,
                })
                delay = self.cfg.interval_sec
                if self.cfg.jitter_sec > 0:
                    delay += random.uniform(0, self.cfg.jitter_sec)
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.exception("Sensor %s crashed: %s", self.id, e)
            await self.on_event({
                "type": "error",
                "sensor_id": self.id,
                "sensor_name": self.cfg.name,
                "message": str(e),
            })

    def status(self) -> SensorStatus:
        return SensorStatus(
            id=self.id,
            name=self.cfg.name,
            interval_sec=self.cfg.interval_sec,
            jitter_sec=self.cfg.jitter_sec,
            running=self.running,
            messages_sent=self.messages_sent,
            errors=self.errors,
            last_payload=self.last_payload,
            last_error=self.last_error,
            outputs_summary=self.last_targets,
            fields=self.cfg.fields,
            outputs=self.cfg.outputs,
            anomaly=self.cfg.anomaly,
        )


class SensorManager:
    def __init__(
        self,
        hub: PublisherHub,
        on_event: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        self.hub = hub
        self.on_event = on_event
        self.sensors: Dict[str, Sensor] = {}
        self._lock = asyncio.Lock()

    # ---- internal helpers --------------------------------------------------

    def _name_in_use(self, name: str, exclude_id: Optional[str] = None) -> bool:
        norm = name.strip().lower()
        for s in self.sensors.values():
            if exclude_id and s.id == exclude_id:
                continue
            if s.cfg.name.strip().lower() == norm:
                return True
        return False

    # ---- CRUD --------------------------------------------------------------

    async def create(self, cfg: SensorConfig) -> Sensor:
        async with self._lock:
            if len(self.sensors) >= MAX_SENSORS:
                raise ValueError(f"Maximum of {MAX_SENSORS} sensors reached")
            if self._name_in_use(cfg.name):
                raise ValueError(f"Sensor name '{cfg.name}' already in use")
            sensor = Sensor(cfg, self.hub, self.on_event)
            self.sensors[sensor.id] = sensor
        if cfg.running:
            await sensor.start()
        await self.on_event({
            "type": "created", "sensor_id": sensor.id, "sensor_name": sensor.cfg.name,
        })
        return sensor

    async def delete(self, sensor_id: str) -> None:
        sensor = self.sensors.get(sensor_id)
        if not sensor:
            return
        await sensor.stop()
        async with self._lock:
            self.sensors.pop(sensor_id, None)
        await self.on_event({
            "type": "deleted", "sensor_id": sensor_id, "sensor_name": sensor.cfg.name,
        })

    async def update(self, sensor_id: str, cfg: SensorConfig) -> Sensor:
        sensor = self.sensors.get(sensor_id)
        if not sensor:
            raise KeyError(sensor_id)
        if self._name_in_use(cfg.name, exclude_id=sensor_id):
            raise ValueError(f"Sensor name '{cfg.name}' already in use")
        was_running = sensor.running
        await sensor.stop()
        cfg.id = sensor_id
        sensor.cfg = cfg
        sensor.state = SensorState()
        if was_running or cfg.running:
            await sensor.start()
        await self.on_event({
            "type": "updated", "sensor_id": sensor.id, "sensor_name": sensor.cfg.name,
        })
        return sensor

    async def clone(self, sensor_id: str) -> Sensor:
        src = self.sensors.get(sensor_id)
        if not src:
            raise KeyError(sensor_id)
        new_cfg = src.cfg.model_copy(deep=True)
        new_cfg.id = None
        new_cfg.running = False
        # find an available name suffix
        base = src.cfg.name
        candidate = f"{base}-copy"
        idx = 2
        while self._name_in_use(candidate):
            candidate = f"{base}-copy-{idx}"
            idx += 1
        new_cfg.name = candidate
        return await self.create(new_cfg)

    # ---- lifecycle ---------------------------------------------------------

    async def start(self, sensor_id: str) -> None:
        s = self.sensors.get(sensor_id)
        if s:
            await s.start()

    async def stop(self, sensor_id: str) -> None:
        s = self.sensors.get(sensor_id)
        if s:
            await s.stop()

    async def start_all(self) -> int:
        n = 0
        for s in self.sensors.values():
            if not s.running:
                await s.start()
                n += 1
        return n

    async def stop_all(self) -> int:
        n = 0
        for s in self.sensors.values():
            if s.running:
                await s.stop()
                n += 1
        return n

    # ---- bulk import / export ---------------------------------------------

    async def replace_all(self, configs: List[SensorConfig]) -> List[Sensor]:
        # validate uniqueness within import payload first
        names = [c.name.strip().lower() for c in configs]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate sensor names in import payload")
        if len(configs) > MAX_SENSORS:
            raise ValueError(f"Import exceeds the {MAX_SENSORS}-sensor limit")
        await self.shutdown()
        created: List[Sensor] = []
        for cfg in configs:
            cfg.id = None  # let manager assign a new id
            created.append(await self.create(cfg))
        return created

    async def import_many(self, configs: List[SensorConfig]) -> List[Sensor]:
        created: List[Sensor] = []
        for cfg in configs:
            cfg.id = None
            # auto-rename on conflict
            base = cfg.name
            candidate = base
            idx = 2
            while self._name_in_use(candidate):
                candidate = f"{base}-{idx}"
                idx += 1
            cfg.name = candidate
            created.append(await self.create(cfg))
        return created

    def list(self) -> List[SensorStatus]:
        return [s.status() for s in self.sensors.values()]

    async def shutdown(self) -> None:
        for s in list(self.sensors.values()):
            await s.stop()
        self.sensors.clear()
