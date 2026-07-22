"""Output publishers for sensor payloads.

Supported sinks: screen · MQTT · Kafka · TCP/JSON · file · HTTP webhook ·
AMQP (RabbitMQ) · CoAP. Each output may optionally encrypt its payload with
AES-256-GCM before sending (see :mod:`app.crypto`).

Protocol client libraries for HTTP/AMQP/CoAP are imported lazily so that a
missing optional dependency only degrades the affected output (surfaced as
``<type>!ERR``) instead of breaking the whole application at import time.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
from typing import Any, Dict, List, Optional, Tuple

import paho.mqtt.client as mqtt
from aiokafka import AIOKafkaProducer

from .crypto import encrypt_payload
from .models import (
    AmqpOutput,
    CoapOutput,
    EncryptionConfig,
    FileOutput,
    HttpOutput,
    KafkaOutput,
    MqttOutput,
    OutputConfig,
    ScreenOutput,
    TcpJsonOutput,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MQTT clients are pooled per (host, port, user, client_id, tls)
# ---------------------------------------------------------------------------

class MqttPool:
    def __init__(self) -> None:
        self._clients: Dict[str, mqtt.Client] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(cfg: MqttOutput) -> str:
        return f"{cfg.host}:{cfg.port}:{cfg.username or ''}:{cfg.client_id or ''}:{int(cfg.tls)}"

    async def publish(self, cfg: MqttOutput, topic: str, payload: str) -> None:
        key = self._key(cfg)
        async with self._lock:
            client = self._clients.get(key)
            if client is None:
                client = mqtt.Client(
                    mqtt.CallbackAPIVersion.VERSION2,
                    client_id=cfg.client_id or "",
                )
                if cfg.username:
                    client.username_pw_set(cfg.username, cfg.password or "")
                if cfg.tls:
                    ctx = ssl.create_default_context()
                    client.tls_set_context(ctx)
                client.connect(cfg.host, cfg.port, keepalive=30)
                client.loop_start()
                self._clients[key] = client
        info = client.publish(topic, payload, qos=cfg.qos, retain=cfg.retain)
        # Surface synchronous publish errors immediately
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish rc={info.rc}")

    async def close(self) -> None:
        async with self._lock:
            for c in self._clients.values():
                try:
                    c.loop_stop()
                    c.disconnect()
                except Exception:
                    pass
            self._clients.clear()


# ---------------------------------------------------------------------------
# Kafka producers pooled per bootstrap servers
# ---------------------------------------------------------------------------

class KafkaPool:
    def __init__(self) -> None:
        self._producers: Dict[str, AIOKafkaProducer] = {}
        self._lock = asyncio.Lock()

    async def publish(self, cfg: KafkaOutput, payload: Dict[str, Any]) -> None:
        async with self._lock:
            prod = self._producers.get(cfg.bootstrap_servers)
            if prod is None:
                prod = AIOKafkaProducer(
                    bootstrap_servers=cfg.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
                    request_timeout_ms=10000,
                )
                await prod.start()
                self._producers[cfg.bootstrap_servers] = prod
        key = None
        if cfg.key_field and cfg.key_field in payload and payload[cfg.key_field] is not None:
            key = str(payload[cfg.key_field])
        await prod.send_and_wait(cfg.topic, payload, key=key)

    async def close(self) -> None:
        async with self._lock:
            for p in self._producers.values():
                try:
                    await p.stop()
                except Exception:
                    pass
            self._producers.clear()


# ---------------------------------------------------------------------------
# HTTP webhook — pooled httpx.AsyncClient per TLS-verify setting
# ---------------------------------------------------------------------------

class HttpPool:
    def __init__(self) -> None:
        self._clients: Dict[bool, Any] = {}
        self._lock = asyncio.Lock()

    async def _client(self, verify: bool):
        import httpx  # lazy

        async with self._lock:
            client = self._clients.get(verify)
            if client is None:
                client = httpx.AsyncClient(verify=verify)
                self._clients[verify] = client
            return client

    async def publish(self, cfg: HttpOutput, text: str) -> None:
        import httpx  # lazy

        client = await self._client(cfg.verify_tls)
        headers = {"Content-Type": "application/json", **cfg.headers}
        if cfg.bearer_token:
            headers["Authorization"] = f"Bearer {cfg.bearer_token}"
        auth = None
        if cfg.basic_user is not None:
            auth = httpx.BasicAuth(cfg.basic_user, cfg.basic_pass or "")
        resp = await client.request(
            cfg.method,
            cfg.url,
            content=text.encode("utf-8"),
            headers=headers,
            auth=auth,
            timeout=cfg.timeout_sec,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} from {cfg.url}")

    async def close(self) -> None:
        async with self._lock:
            for c in self._clients.values():
                try:
                    await c.aclose()
                except Exception:
                    pass
            self._clients.clear()


# ---------------------------------------------------------------------------
# AMQP (RabbitMQ) — robust connection pooled per URL
# ---------------------------------------------------------------------------

class AmqpPool:
    def __init__(self) -> None:
        self._channels: Dict[str, Any] = {}
        self._connections: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def publish(self, cfg: AmqpOutput, routing_key: str, text: str) -> None:
        import aio_pika  # lazy

        async with self._lock:
            channel = self._channels.get(cfg.url)
            if channel is None or channel.is_closed:
                conn = await aio_pika.connect_robust(cfg.url)
                channel = await conn.channel()
                self._connections[cfg.url] = conn
                self._channels[cfg.url] = channel
        message = aio_pika.Message(
            body=text.encode("utf-8"),
            content_type="application/json",
        )
        if cfg.exchange:
            exchange = await channel.declare_exchange(
                cfg.exchange, aio_pika.ExchangeType.TOPIC, durable=True
            )
            await exchange.publish(message, routing_key=routing_key)
        else:
            await channel.default_exchange.publish(message, routing_key=routing_key)

    async def close(self) -> None:
        async with self._lock:
            for conn in self._connections.values():
                try:
                    await conn.close()
                except Exception:
                    pass
            self._channels.clear()
            self._connections.clear()


# ---------------------------------------------------------------------------
# CoAP — one shared client context
# ---------------------------------------------------------------------------

class CoapClient:
    def __init__(self) -> None:
        self._ctx: Any = None
        self._lock = asyncio.Lock()

    async def publish(self, cfg: CoapOutput, text: str) -> None:
        import aiocoap  # lazy

        async with self._lock:
            if self._ctx is None:
                self._ctx = await aiocoap.Context.create_client_context()
        code = aiocoap.POST if cfg.method == "POST" else aiocoap.PUT
        request = aiocoap.Message(code=code, uri=cfg.uri, payload=text.encode("utf-8"))
        await asyncio.wait_for(self._ctx.request(request).response, timeout=5.0)

    async def close(self) -> None:
        async with self._lock:
            if self._ctx is not None:
                try:
                    await self._ctx.shutdown()
                except Exception:
                    pass
                self._ctx = None


# ---------------------------------------------------------------------------
# TCP/JSON sink (newline-delimited)
# ---------------------------------------------------------------------------

async def tcp_json_send(cfg: TcpJsonOutput, text: str) -> None:
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(cfg.host, cfg.port), timeout=5.0
    )
    try:
        writer.write((text + "\n").encode("utf-8"))
        await writer.drain()
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


def _write_file_sync(cfg: FileOutput, payload: Dict[str, Any]) -> None:
    """Synchronous file write — called via asyncio.to_thread."""
    dir_path = os.path.dirname(cfg.path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    write_mode = "a" if cfg.mode == "append" else "w"
    line = (
        json.dumps(payload, indent=2, ensure_ascii=False)
        if cfg.format == "json_pretty"
        else json.dumps(payload, ensure_ascii=False)
    )
    with open(cfg.path, write_mode, encoding="utf-8") as fh:
        fh.write(line + "\n")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def _apply_encryption(
    payload: Dict[str, Any],
    enc: Optional[EncryptionConfig],
    sensor_name: str,
) -> Tuple[Dict[str, Any], str]:
    """Return (effective_payload, effective_text) after optional encryption."""
    text = json.dumps(payload, ensure_ascii=False)
    if enc and enc.enabled:
        envelope = encrypt_payload(payload, text, enc, aad=sensor_name)
        return envelope, json.dumps(envelope, ensure_ascii=False)
    return payload, text


class PublisherHub:
    def __init__(self) -> None:
        self.mqtt = MqttPool()
        self.kafka = KafkaPool()
        self.http = HttpPool()
        self.amqp = AmqpPool()
        self.coap = CoapClient()
        self.total_messages = 0
        self.total_errors = 0

    async def dispatch(
        self,
        sensor_name: str,
        outputs: List[OutputConfig],
        payload: Dict[str, Any],
    ) -> List[str]:
        targets: List[str] = []
        for out in outputs:
            if not getattr(out, "enabled", True):
                continue
            enc = getattr(out, "encryption", None)
            try:
                eff_payload, text = _apply_encryption(payload, enc, sensor_name)
                enc_tag = "🔒" if (enc and enc.enabled) else ""
                if isinstance(out, ScreenOutput):
                    targets.append("screen" + enc_tag)
                elif isinstance(out, MqttOutput):
                    topic = out.topic.replace("{sensor}", sensor_name)
                    await self.mqtt.publish(out, topic, text)
                    targets.append(f"mqtt({out.host}:{out.port}/{topic}){enc_tag}")
                elif isinstance(out, KafkaOutput):
                    await self.kafka.publish(out, eff_payload)
                    targets.append(f"kafka({out.bootstrap_servers}/{out.topic}){enc_tag}")
                elif isinstance(out, TcpJsonOutput):
                    await tcp_json_send(out, text)
                    targets.append(f"tcp({out.host}:{out.port}){enc_tag}")
                elif isinstance(out, FileOutput):
                    await asyncio.to_thread(_write_file_sync, out, eff_payload)
                    targets.append(f"file({out.path}){enc_tag}")
                elif isinstance(out, HttpOutput):
                    await self.http.publish(out, text)
                    targets.append(f"http({out.method} {out.url}){enc_tag}")
                elif isinstance(out, AmqpOutput):
                    rk = out.routing_key.replace("{sensor}", sensor_name)
                    await self.amqp.publish(out, rk, text)
                    targets.append(f"amqp({rk}){enc_tag}")
                elif isinstance(out, CoapOutput):
                    await self.coap.publish(out, text)
                    targets.append(f"coap({out.uri}){enc_tag}")
                self.total_messages += 1
            except Exception as e:  # noqa: BLE001
                self.total_errors += 1
                logger.error("Output %s failed: %s", out.type, e)
                targets.append(f"{out.type}!ERR")
        return targets

    async def close(self) -> None:
        await self.mqtt.close()
        await self.kafka.close()
        await self.http.close()
        await self.amqp.close()
        await self.coap.close()
