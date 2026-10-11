"""HTTP ingest, runtime port map, and import capacity guard."""
from app.main import bus


def test_runtime_exposes_port_standard(client):
    body = client.get("/api/runtime").json()
    assert body["version"] == "1.3.0"
    assert body["ports"]["http"]["port"] == 8000
    assert body["ports"]["tcp_json"]["port"] == 5050
    assert body["ports"]["mqtt"]["port"] == 1883
    assert body["ports"]["kafka"]["port"] == 9092
    assert body["ports"]["amqp"]["port"] == 5672
    assert body["ports"]["coap"]["port"] == 5683
    assert "mqtt" in body["defaults"]
    assert body["defaults"]["http"]["url"].endswith("/api/ingest")


def test_http_ingest_accepted(client):
    r = client.post("/api/ingest", json={"temp": 21.5, "id": "x"})
    assert r.status_code == 202
    assert r.json()["status"] == "accepted"


def test_http_ingest_published_on_bus(client):
    assert client.post("/api/ingest", json={"n": 1}).status_code == 202
    matches = [
        e for e in bus.buffer
        if e.get("type") == "ingress" and e.get("payload") == {"n": 1}
    ]
    assert matches
    assert matches[-1]["source"].startswith("http:")


def test_import_rejects_over_capacity(client, monkeypatch):
    monkeypatch.setattr("app.sensors.MAX_SENSORS", 2)
    from tests.test_api import _sensor

    assert client.post("/api/sensors", json=_sensor("a")).status_code == 201
    r = client.post("/api/config/import", json={
        "replace": False,
        "sensors": [_sensor("b"), _sensor("c")],
    })
    assert r.status_code == 400
    names = {s["name"] for s in client.get("/api/sensors").json()}
    assert names == {"a"}
