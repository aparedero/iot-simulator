"""Bundled-example host rewrite."""
from app.examples import rewrite_output, rewrite_sensors


def test_rewrite_off_leaves_hosts(monkeypatch):
    monkeypatch.setenv("IOTSIM_REWRITE_EXAMPLE_HOSTS", "0")
    out = rewrite_output({
        "type": "mqtt", "host": "broker.hivemq.com", "port": 1883,
    })
    assert out["host"] == "broker.hivemq.com"


def test_rewrite_mqtt_and_kafka(monkeypatch):
    monkeypatch.setenv("IOTSIM_REWRITE_EXAMPLE_HOSTS", "1")
    monkeypatch.setenv("IOTSIM_MQTT_HOST", "mqtt")
    monkeypatch.setenv("IOTSIM_MQTT_PORT", "1883")
    monkeypatch.setenv("IOTSIM_KAFKA_BOOTSTRAP", "kafka:9092")
    mqtt = rewrite_output({"type": "mqtt", "host": "broker.hivemq.com", "port": 1883})
    assert mqtt["host"] == "mqtt"
    kafka = rewrite_output({
        "type": "kafka", "bootstrap_servers": "localhost:9092", "topic": "t",
    })
    assert kafka["bootstrap_servers"] == "kafka:9092"


def test_rewrite_http_uses_runtime_ingest(monkeypatch):
    monkeypatch.setenv("IOTSIM_REWRITE_EXAMPLE_HOSTS", "1")
    monkeypatch.setenv("IOTSIM_HTTP_INGEST_URL", "http://iot-sim:8000/api/ingest")
    out = rewrite_output({
        "type": "http", "url": "http://localhost:9000/ingest", "method": "POST",
    })
    assert out["url"] == "http://iot-sim:8000/api/ingest"


def test_rewrite_sensors_copies(monkeypatch):
    monkeypatch.setenv("IOTSIM_REWRITE_EXAMPLE_HOSTS", "1")
    monkeypatch.setenv("IOTSIM_MQTT_HOST", "mqtt")
    src = [{"name": "s", "outputs": [{"type": "mqtt", "host": "localhost"}]}]
    out = rewrite_sensors(src)
    assert src[0]["outputs"][0]["host"] == "localhost"
    assert out[0]["outputs"][0]["host"] == "mqtt"
