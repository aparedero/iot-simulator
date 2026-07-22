"""Tests for the field value generators."""
import uuid as uuidlib

from app.generators import SensorState, build_payload, generate_value
from app.models import SensorConfig


def _state():
    return SensorState()


def test_basic_types():
    cfg = SensorConfig(name="s", fields=[
        {"type": "timestamp", "name": "ts", "fmt": "epoch_ms"},
        {"type": "fixed_number", "name": "fx", "value": 7},
        {"type": "random_number", "name": "rn", "min": 1, "max": 2, "decimals": 3},
        {"type": "fixed_string", "name": "fs", "value": "hi"},
        {"type": "random_string", "name": "rs", "length": 6, "charset": "hex"},
    ])
    p = build_payload(cfg.fields, _state())
    assert isinstance(p["ts"], int)
    assert p["fx"] == 7
    assert 1 <= p["rn"] <= 2
    assert p["fs"] == "hi"
    assert len(p["rs"]) == 6 and all(c in "0123456789abcdef" for c in p["rs"])


def test_pattern_string_tokens():
    cfg = SensorConfig(name="s", fields=[
        {"type": "pattern_string", "name": "id", "pattern": "DEV-{d:3}-{seq}"},
    ])
    st = _state()
    v1 = build_payload(cfg.fields, st)["id"]
    v2 = build_payload(cfg.fields, st)["id"]
    assert v1.startswith("DEV-") and v1.endswith("-1")
    assert v2.endswith("-2")  # seq increments per field


def test_gaussian_clamped():
    cfg = SensorConfig(name="s", fields=[
        {"type": "gaussian_number", "name": "g", "mean": 0, "stddev": 100,
         "min": -1, "max": 1, "decimals": 4},
    ])
    st = _state()
    for _ in range(200):
        v = build_payload(cfg.fields, st)["g"]
        assert -1 <= v <= 1


def test_random_walk_bounds_and_drift():
    cfg = SensorConfig(name="s", fields=[
        {"type": "random_walk", "name": "w", "start": 50, "step": 5,
         "min": 0, "max": 100, "decimals": 2},
    ])
    st = _state()
    prev = None
    for _ in range(500):
        v = build_payload(cfg.fields, st)["w"]
        assert 0 <= v <= 100
        if prev is not None:
            assert abs(v - prev) <= 5.001  # never jumps more than step
        prev = v


def test_sine_wave_range():
    cfg = SensorConfig(name="s", fields=[
        {"type": "sine_wave", "name": "s", "amplitude": 10, "offset": 20,
         "period_sec": 60, "noise": 0, "decimals": 4},
    ])
    st = _state()
    for _ in range(50):
        v = build_payload(cfg.fields, st)["s"]
        assert 10 - 1e-6 <= v <= 30 + 1e-6


def test_boolean_and_enum_weights():
    cfg = SensorConfig(name="s", fields=[
        {"type": "boolean", "name": "b", "p_true": 1.0},
        {"type": "enum", "name": "e", "values": ["only"], "weights": [1]},
    ])
    p = build_payload(cfg.fields, _state())
    assert p["b"] is True
    assert p["e"] == "only"


def test_uuid_and_geo_point():
    cfg = SensorConfig(name="s", fields=[
        {"type": "uuid", "name": "u"},
        {"type": "geo_point", "name": "loc", "lat": 40.0, "lon": -3.0,
         "radius_m": 100, "decimals": 6},
    ])
    p = build_payload(cfg.fields, _state())
    uuidlib.UUID(p["u"])  # raises if invalid
    assert set(p["loc"]) == {"lat", "lon"}
    # within ~ 100 m => < 0.01 deg latitude
    assert abs(p["loc"]["lat"] - 40.0) < 0.01
    assert abs(p["loc"]["lon"] - (-3.0)) < 0.01


def test_file_modes(tmp_path):
    f = tmp_path / "vals.txt"
    f.write_text("a\nb\nc\n", encoding="utf-8")
    st = _state()
    field = {"type": "file", "name": "v", "path": str(f), "mode": "sequential"}
    cfg = SensorConfig(name="s", fields=[field])
    got = [build_payload(cfg.fields, st)["v"] for _ in range(4)]
    assert got[:3] == ["a", "b", "c"]
    assert got[3] is None  # sequential stops at EOF
