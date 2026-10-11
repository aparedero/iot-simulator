"""Rewrite bundled-example output hosts to the runtime defaults."""
from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import urlparse, urlunparse

from . import settings


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "broker.hivemq.com"}


def _host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def rewrite_output(out: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of an output dict with lab hosts applied when needed."""
    if not settings.rewrite_example_hosts():
        return out
    kind = out.get("type")
    defaults = settings.output_defaults()
    updated = dict(out)
    if kind == "mqtt":
        host = (updated.get("host") or "").lower()
        if host in _LOCAL_HOSTS or not host:
            updated["host"] = defaults["mqtt"]["host"]
            updated["port"] = defaults["mqtt"]["port"]
    elif kind == "kafka":
        servers = (updated.get("bootstrap_servers") or "").lower()
        if servers.startswith("localhost") or servers.startswith("127.0.0.1"):
            updated["bootstrap_servers"] = defaults["kafka"]["bootstrap_servers"]
    elif kind == "tcp_json":
        host = (updated.get("host") or "").lower()
        if host in _LOCAL_HOSTS or not host:
            updated["host"] = defaults["tcp_json"]["host"]
            updated["port"] = defaults["tcp_json"]["port"]
    elif kind == "http":
        if _host_of(updated.get("url") or "") in _LOCAL_HOSTS:
            updated["url"] = defaults["http"]["url"]
    elif kind == "amqp":
        if _host_of(updated.get("url") or "") in _LOCAL_HOSTS:
            updated["url"] = defaults["amqp"]["url"]
    elif kind == "coap":
        if _host_of(updated.get("uri") or "") in _LOCAL_HOSTS:
            path = urlparse(updated.get("uri") or "").path or "/ingest"
            base = urlparse(defaults["coap"]["uri"])
            updated["uri"] = urlunparse((
                base.scheme, base.netloc, path, "", "", "",
            ))
    return updated


def rewrite_sensors(sensors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for sensor in sensors:
        item = dict(sensor)
        item["outputs"] = [rewrite_output(o) for o in (sensor.get("outputs") or [])]
        out.append(item)
    return out
