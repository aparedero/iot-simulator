"""End-to-end API tests via FastAPI TestClient."""
import io
import json
from pathlib import Path

import yaml

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def _sensor(name="temp-1", running=False):
    return {
        "name": name,
        "interval_sec": 1,
        "running": running,
        "fields": [
            {"type": "timestamp", "name": "ts", "fmt": "iso"},
            {"type": "random_number", "name": "t", "min": 0, "max": 1, "decimals": 2},
        ],
        "outputs": [{"type": "screen", "enabled": True}],
    }


def test_health_and_metrics(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok"
    assert h["version"] == "1.2.0"
    m = client.get("/api/metrics").json()
    assert m["sensors_total"] == 0


def test_prometheus_metrics(client):
    client.post("/api/sensors", json=_sensor())
    body = client.get("/metrics").text
    assert "iotsim_uptime_seconds" in body
    assert "iotsim_sensor_messages_total{" in body
    assert body.rstrip().endswith("}") or "iotsim_sensors " in body


def test_crud_lifecycle(client):
    r = client.post("/api/sensors", json=_sensor())
    assert r.status_code == 201
    sid = r.json()["id"]

    assert client.get(f"/api/sensors/{sid}").status_code == 200
    assert len(client.get("/api/sensors").json()) == 1

    # update
    upd = _sensor(name="temp-1", running=False)
    upd["interval_sec"] = 5
    r = client.put(f"/api/sensors/{sid}", json=upd)
    assert r.json()["interval_sec"] == 5

    # start/stop
    assert client.post(f"/api/sensors/{sid}/start").json()["running"] is True
    assert client.post(f"/api/sensors/{sid}/stop").json()["running"] is False

    # clone
    r = client.post(f"/api/sensors/{sid}/clone")
    assert r.status_code == 201
    assert r.json()["name"] == "temp-1-copy"

    # delete
    assert client.delete(f"/api/sensors/{sid}").status_code == 204
    assert client.get(f"/api/sensors/{sid}").status_code == 404


def test_duplicate_name_rejected(client):
    client.post("/api/sensors", json=_sensor())
    r = client.post("/api/sensors", json=_sensor())
    assert r.status_code == 400


def test_bad_config_rejected(client):
    bad = _sensor()
    bad["name"] = ""
    assert client.post("/api/sensors", json=bad).status_code == 422


def test_export_import_json_roundtrip(client):
    client.post("/api/sensors", json=_sensor("a"))
    client.post("/api/sensors", json=_sensor("b"))
    exported = client.get("/api/config/export").json()
    assert len(exported["sensors"]) == 2

    client.delete("/api/sensors")
    r = client.post("/api/config/import", json={"sensors": exported["sensors"], "replace": True})
    assert r.json()["imported"] == 2


def test_export_yaml_and_import_raw(client):
    client.post("/api/sensors", json=_sensor("yaml-sensor"))
    text = client.get("/api/config/export?format=yaml").text
    doc = yaml.safe_load(text)
    assert doc["sensors"][0]["name"] == "yaml-sensor"

    client.delete("/api/sensors")
    r = client.post("/api/config/import-raw?replace=true", content=text,
                    headers={"Content-Type": "text/plain"})
    assert r.status_code == 200
    assert r.json()["imported"] == 1
    assert client.get("/api/sensors").json()[0]["name"] == "yaml-sensor"


def test_import_auto_rename(client):
    client.post("/api/sensors", json=_sensor("dup"))
    r = client.post("/api/config/import", json={"sensors": [_sensor("dup")], "replace": False})
    assert r.json()["imported"] == 1
    names = {s["name"] for s in client.get("/api/sensors").json()}
    assert names == {"dup", "dup-2"}


def test_examples_endpoint(client):
    examples = client.get("/api/examples").json()
    ids = {e["id"] for e in examples}
    assert {"smart-building", "fleet-gps", "industrial-machine",
            "energy-meter", "air-quality"} <= ids


def test_import_each_example(client):
    for e in client.get("/api/examples").json():
        r = client.post(f"/api/examples/{e['id']}/import?replace=true")
        assert r.status_code == 200, e["id"]
        assert r.json()["imported"] >= 1


def test_example_path_traversal_blocked(client):
    assert client.post("/api/examples/..%2f..%2fetc%2fpasswd/import").status_code in (400, 404)


def test_all_example_files_valid():
    """Every bundled example must be valid, importable SensorConfig JSON."""
    from app.models import SensorConfig

    files = list(EXAMPLES_DIR.glob("*.json"))
    assert files, "no example files found"
    for f in files:
        data = json.loads(f.read_text())
        assert "sensors" in data and data["sensors"], f.name
        for s in data["sensors"]:
            SensorConfig(**s)  # raises on invalid config
