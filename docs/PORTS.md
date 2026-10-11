# Communication port standard

These ports are the default contract for the simulator and the lab stack.
Keep them unless you have a port conflict.

| Name | Port | Protocol | Role |
|------|------|----------|------|
| HTTP | 8000 | TCP | Web UI, REST API, WebSocket `/ws`, HTTP ingest `POST /api/ingest` |
| TCP/JSON | 5050 | TCP | Newline-delimited JSON ingress |
| MQTT | 1883 | TCP | MQTT broker |
| MQTT TLS | 8883 | TCP | MQTT over TLS (broker-side; optional) |
| Kafka | 9092 | TCP | Kafka / Redpanda |
| AMQP | 5672 | TCP | RabbitMQ AMQP 0-9-1 |
| AMQP management | 15672 | TCP | RabbitMQ management UI |
| CoAP | 5683 | UDP | CoAP ingest (`/ingest`) |

The running process also publishes this map at `GET /api/runtime`.

## Docker Compose

`docker compose up --build` publishes every port in the table except MQTT TLS.

- Simulator: `8000`, `5050`, `5683/udp`
- Mosquitto: `1883`
- Redpanda: host `9092` → container `19092` (clients on the host use `localhost:9092`; the simulator uses `kafka:9092`)
- RabbitMQ: `5672` and `15672` (user `iot` / `iot`, lab-only)

## Helm

The chart Service type defaults to `NodePort`:

| Port | NodePort |
|------|----------|
| 8000 | 30080 |
| 5050 | 30550 |
| 5683/udp | 30583 |

Disable NodePort names by switching `service.type` to `ClusterIP` or `LoadBalancer`.
Set `ingress.enabled=true` when you want an HTTP Ingress in front of port 8000.

## Clients

```bash
# HTTP ingest
curl -X POST http://localhost:8000/api/ingest -H 'Content-Type: application/json' -d '{"temp":21}'

# TCP/JSON ingress
echo '{"sensor":"ext-01","value":42}' | nc localhost 5050

# MQTT
mosquitto_sub -h localhost -t 'iot/sim/#' -v

# Kafka (after compose is up)
# any client to localhost:9092 topic iot-sim / iot-machines

# AMQP management
# http://localhost:15672  (iot / iot)
```
