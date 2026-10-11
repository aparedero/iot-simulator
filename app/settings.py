"""Runtime configuration from environment variables.

Port numbers in ``PORTS`` are the project communication standard.
See docs/PORTS.md.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Canonical port map (documentation + /api/runtime). Independent of env.
PORTS = {
    "http": {"port": 8000, "protocol": "TCP", "role": "Web UI, REST API, WebSocket, HTTP ingest"},
    "tcp_json": {"port": 5050, "protocol": "TCP", "role": "Newline-delimited JSON ingress"},
    "mqtt": {"port": 1883, "protocol": "TCP", "role": "MQTT broker"},
    "mqtt_tls": {"port": 8883, "protocol": "TCP", "role": "MQTT over TLS"},
    "kafka": {"port": 9092, "protocol": "TCP", "role": "Kafka / Redpanda broker"},
    "amqp": {"port": 5672, "protocol": "TCP", "role": "AMQP 0-9-1 (RabbitMQ)"},
    "amqp_management": {"port": 15672, "protocol": "TCP", "role": "RabbitMQ management UI"},
    "coap": {"port": 5683, "protocol": "UDP", "role": "CoAP ingest"},
}


def _int_env(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def _flag_env(name: str, default: str = "1") -> bool:
    return os.getenv(name, default) not in ("0", "false", "False", "")


def http_host() -> str:
    return os.getenv("HTTP_HOST", "0.0.0.0")


def http_port() -> int:
    return _int_env("HTTP_PORT", "8000")


def listen_host() -> str:
    return os.getenv("LISTEN_HOST", "0.0.0.0")


def listen_port() -> int:
    return _int_env("LISTEN_PORT", "5050")


def coap_listen_port() -> int:
    return _int_env("COAP_LISTEN_PORT", "5683")


def log_level() -> str:
    return os.getenv("LOG_LEVEL", "INFO")


def mqtt_host() -> str:
    return os.getenv("IOTSIM_MQTT_HOST", "localhost")


def mqtt_port() -> int:
    return _int_env("IOTSIM_MQTT_PORT", "1883")


def kafka_bootstrap() -> str:
    return os.getenv("IOTSIM_KAFKA_BOOTSTRAP", "localhost:9092")


def amqp_url() -> str:
    return os.getenv("IOTSIM_AMQP_URL", "amqp://iot:iot@localhost:5672/")


def coap_uri() -> str:
    return os.getenv("IOTSIM_COAP_URI", "coap://localhost:5683/ingest")


def http_ingest_url() -> str:
    return os.getenv("IOTSIM_HTTP_INGEST_URL", "http://127.0.0.1:8000/api/ingest")


def tcp_json_host() -> str:
    return os.getenv("IOTSIM_TCP_JSON_HOST", "127.0.0.1")


def tcp_json_port() -> int:
    return _int_env("IOTSIM_TCP_JSON_PORT", "5050")


def rewrite_example_hosts() -> bool:
    # Off by default so local runs keep public MQTT brokers in bundled examples.
    # docker-compose sets this to 1 so examples target in-stack brokers.
    return _flag_env("IOTSIM_REWRITE_EXAMPLE_HOSTS", "0")


def file_field_root() -> Path:
    return Path(os.getenv("IOTSIM_FILE_FIELD_ROOT", str(BASE_DIR / "sample_data"))).resolve()


def file_output_root() -> Path:
    return Path(os.getenv("IOTSIM_FILE_OUTPUT_ROOT", str(BASE_DIR / "output"))).resolve()


def output_defaults() -> dict:
    """Default output connection settings exposed to the UI and examples."""
    return {
        "mqtt": {"host": mqtt_host(), "port": mqtt_port(), "topic": "iot/sim/{sensor}"},
        "kafka": {"bootstrap_servers": kafka_bootstrap(), "topic": "iot-sim"},
        "tcp_json": {"host": tcp_json_host(), "port": tcp_json_port()},
        "http": {"url": http_ingest_url(), "method": "POST"},
        "amqp": {"url": amqp_url(), "exchange": "", "routing_key": "iot.sim.{sensor}"},
        "coap": {"uri": coap_uri(), "method": "POST"},
        "file_output": {"path": "sensor.jsonl", "mode": "append", "format": "jsonl"},
    }


def runtime_info(version: str) -> dict:
    return {
        "version": version,
        "ports": PORTS,
        "listen": {
            "http_port": http_port(),
            "tcp_json_host": listen_host(),
            "tcp_json_port": listen_port(),
            "coap_port": coap_listen_port(),
        },
        "defaults": output_defaults(),
        "rewrite_example_hosts": rewrite_example_hosts(),
        "file_field_root": str(file_field_root()),
        "file_output_root": str(file_output_root()),
    }
