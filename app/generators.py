"""Field value generators."""
from __future__ import annotations

import math
import os
import random
import re
import string
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import FieldConfig


_FILE_CACHE: Dict[str, List[str]] = {}
_FILE_LOCK = threading.Lock()


def _load_file(path: str) -> List[str]:
    with _FILE_LOCK:
        if path in _FILE_CACHE:
            return _FILE_CACHE[path]
        if not os.path.exists(path):
            _FILE_CACHE[path] = []
            return []
        with open(path, "r", encoding="utf-8") as fh:
            lines = [ln.rstrip("\n") for ln in fh if ln.strip() != ""]
        _FILE_CACHE[path] = lines
        return lines


_PATTERN_TOKEN = re.compile(r"\{([^{}]+)\}")


class FieldState:
    """Per-field mutable state (file reads, counters, random-walk position)."""

    def __init__(self) -> None:
        self.file_index: int = 0
        self.seq: int = 0
        self.walk: Optional[float] = None  # current random-walk position


class SensorState:
    def __init__(self) -> None:
        self.fields: Dict[str, FieldState] = {}
        self.start_ts: float = time.monotonic()  # for periodic (sine) fields

    def field(self, name: str) -> FieldState:
        if name not in self.fields:
            self.fields[name] = FieldState()
        return self.fields[name]

    def elapsed(self) -> float:
        return time.monotonic() - self.start_ts


def _now(fmt: str) -> Any:
    now = datetime.now(timezone.utc)
    if fmt == "epoch_ms":
        return int(now.timestamp() * 1000)
    if fmt == "epoch_s":
        return int(now.timestamp())
    return now.isoformat()


def _random_string(length: int, charset: str) -> str:
    pools = {
        "alpha": string.ascii_letters,
        "alnum": string.ascii_letters + string.digits,
        "hex": string.hexdigits.lower()[:16],
        "digits": string.digits,
    }
    pool = pools.get(charset, pools["alnum"])
    return "".join(random.choice(pool) for _ in range(length))


def _expand_pattern(pattern: str, fs: FieldState) -> str:
    def repl(match: re.Match) -> str:
        tok = match.group(1)
        if ":" in tok:
            kind, arg = tok.split(":", 1)
        else:
            kind, arg = tok, ""
        kind = kind.strip()
        if kind == "d":
            n = int(arg or "1")
            return "".join(random.choice(string.digits) for _ in range(n))
        if kind == "a":
            n = int(arg or "1")
            return "".join(random.choice(string.ascii_letters) for _ in range(n))
        if kind == "h":
            n = int(arg or "1")
            return "".join(random.choice(string.hexdigits.lower()[:16]) for _ in range(n))
        if kind == "choice":
            options = [o for o in arg.split("|") if o]
            return random.choice(options) if options else ""
        if kind == "seq":
            fs.seq += 1
            return str(fs.seq)
        return match.group(0)
    return _PATTERN_TOKEN.sub(repl, pattern)


def generate_value(field: FieldConfig, state: SensorState) -> Any:
    fs = state.field(field.name)
    t = field.type
    if t == "timestamp":
        return _now(field.fmt)
    if t == "fixed_number":
        return field.value
    if t == "random_number":
        v = random.uniform(field.min, field.max)
        return round(v, field.decimals) if field.decimals >= 0 else v
    if t == "fixed_string":
        return field.value
    if t == "random_string":
        return _random_string(field.length, field.charset)
    if t == "pattern_string":
        return _expand_pattern(field.pattern, fs)
    if t == "file":
        lines = _load_file(field.path)
        if not lines:
            return None
        if field.mode == "random":
            return random.choice(lines)
        # sequential / loop
        idx = fs.file_index
        if idx >= len(lines):
            if field.mode == "sequential":
                return None
            idx = 0
        value = lines[idx]
        fs.file_index = idx + 1
        if field.mode == "loop" and fs.file_index >= len(lines):
            fs.file_index = 0
        return value
    if t == "gaussian_number":
        v = random.gauss(field.mean, field.stddev)
        if field.min is not None:
            v = max(field.min, v)
        if field.max is not None:
            v = min(field.max, v)
        return round(v, field.decimals) if field.decimals >= 0 else v
    if t == "random_walk":
        if fs.walk is None:
            fs.walk = field.start
        fs.walk += random.uniform(-field.step, field.step)
        fs.walk = max(field.min, min(field.max, fs.walk))
        return round(fs.walk, field.decimals) if field.decimals >= 0 else fs.walk
    if t == "sine_wave":
        elapsed = state.elapsed()
        v = field.offset + field.amplitude * math.sin(
            2 * math.pi * (elapsed / field.period_sec) + field.phase
        )
        if field.noise:
            v += random.uniform(-field.noise, field.noise)
        return round(v, field.decimals) if field.decimals >= 0 else v
    if t == "boolean":
        return random.random() < field.p_true
    if t == "enum":
        if field.weights:
            return random.choices(field.values, weights=field.weights, k=1)[0]
        return random.choice(field.values)
    if t == "uuid":
        return str(uuid.uuid4())
    if t == "geo_point":
        # Offset uniformly within a disc of radius_m around the center.
        r = field.radius_m * math.sqrt(random.random())
        theta = random.uniform(0, 2 * math.pi)
        d_lat = (r * math.cos(theta)) / 111_320.0
        cos_lat = math.cos(math.radians(field.lat)) or 1e-9
        d_lon = (r * math.sin(theta)) / (111_320.0 * cos_lat)
        return {
            "lat": round(field.lat + d_lat, field.decimals),
            "lon": round(field.lon + d_lon, field.decimals),
        }
    return None


def build_payload(fields: List[FieldConfig], state: SensorState) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for f in fields:
        payload[f.name] = generate_value(f, state)
    return payload
