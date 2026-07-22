"""Pydantic models describing the configuration of sensors and fields."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Field generators
# ---------------------------------------------------------------------------

class TimestampField(BaseModel):
    type: Literal["timestamp"] = "timestamp"
    name: str = "timestamp"
    fmt: Literal["iso", "epoch_ms", "epoch_s"] = "iso"


class FixedNumberField(BaseModel):
    type: Literal["fixed_number"] = "fixed_number"
    name: str
    value: float


class RandomNumberField(BaseModel):
    type: Literal["random_number"] = "random_number"
    name: str
    min: float = 0
    max: float = 100
    decimals: int = 2


class FixedStringField(BaseModel):
    type: Literal["fixed_string"] = "fixed_string"
    name: str
    value: str


class RandomStringField(BaseModel):
    type: Literal["random_string"] = "random_string"
    name: str
    length: int = 8
    charset: Literal["alpha", "alnum", "hex", "digits"] = "alnum"


class PatternStringField(BaseModel):
    """A string built from a pattern with tokens between braces.

    Supported tokens:
      {d:N}           -> N random digits
      {a:N}           -> N random letters
      {h:N}           -> N hex chars
      {choice:a|b|c}  -> picks one literal at random
      {seq}           -> incremental counter (per-field)
    """
    type: Literal["pattern_string"] = "pattern_string"
    name: str
    pattern: str = "DEV-{d:4}"


class FileField(BaseModel):
    type: Literal["file"] = "file"
    name: str
    path: str
    mode: Literal["sequential", "random", "loop"] = "loop"


class GaussianNumberField(BaseModel):
    """Normally-distributed value — realistic sensor noise around a mean."""
    type: Literal["gaussian_number"] = "gaussian_number"
    name: str
    mean: float = 0.0
    stddev: float = 1.0
    decimals: int = 2
    min: Optional[float] = None  # optional clamp
    max: Optional[float] = None


class RandomWalkField(BaseModel):
    """Random-walk value — the reading drifts by a random step each sample.

    Models slow-moving quantities (temperature, tank level, battery) far more
    realistically than an independent uniform draw on every tick.
    """
    type: Literal["random_walk"] = "random_walk"
    name: str
    start: float = 0.0
    step: float = 1.0  # max absolute change per sample
    min: float = 0.0
    max: float = 100.0
    decimals: int = 2


class SineWaveField(BaseModel):
    """Deterministic periodic signal — e.g. daily temperature/energy cycles.

    value = offset + amplitude * sin(2*pi * (t / period_sec) + phase) + noise
    where ``t`` is the seconds elapsed since the sensor started.
    """
    type: Literal["sine_wave"] = "sine_wave"
    name: str
    amplitude: float = 1.0
    offset: float = 0.0
    period_sec: float = Field(60.0, gt=0.0)
    phase: float = 0.0  # radians
    noise: float = 0.0  # +/- uniform noise added on top
    decimals: int = 2


class BooleanField(BaseModel):
    """Boolean flag that is True with probability ``p_true``."""
    type: Literal["boolean"] = "boolean"
    name: str
    p_true: float = Field(0.5, ge=0.0, le=1.0)


class EnumField(BaseModel):
    """Categorical value picked from ``values`` (optionally weighted)."""
    type: Literal["enum"] = "enum"
    name: str
    values: List[str] = Field(default_factory=lambda: ["ok", "warn", "fault"])
    weights: Optional[List[float]] = None

    @model_validator(mode="after")
    def _check(self) -> "EnumField":
        if not self.values:
            raise ValueError("enum field requires at least one value")
        if self.weights is not None and len(self.weights) != len(self.values):
            raise ValueError("weights length must match values length")
        return self


class UuidField(BaseModel):
    """Random UUID (version 4), useful for message/event ids."""
    type: Literal["uuid"] = "uuid"
    name: str = "uuid"


class GeoPointField(BaseModel):
    """GPS coordinate jittered within ``radius_m`` of a center point.

    Emits a nested object ``{"lat": ..., "lon": ...}`` — the shape most
    fleet/asset-tracking pipelines expect.
    """
    type: Literal["geo_point"] = "geo_point"
    name: str = "location"
    lat: float = 40.4168
    lon: float = -3.7038
    radius_m: float = Field(500.0, ge=0.0)
    decimals: int = 6


FieldConfig = Union[
    TimestampField,
    FixedNumberField,
    RandomNumberField,
    FixedStringField,
    RandomStringField,
    PatternStringField,
    FileField,
    GaussianNumberField,
    RandomWalkField,
    SineWaveField,
    BooleanField,
    EnumField,
    UuidField,
    GeoPointField,
]


# ---------------------------------------------------------------------------
# Optional payload encryption (applied per-output before sending)
# ---------------------------------------------------------------------------

class EncryptionConfig(BaseModel):
    """Optional AES-256-GCM envelope encryption for an output's payload.

    When enabled, the JSON payload is encrypted and replaced with an envelope::

        {"enc": "AES-256-GCM", "iv": "<b64>", "ct": "<b64>", "tag": "<b64>",
         "aad": "<sensor-name>"}

    The 256-bit key is provided either directly as base64 (``key_b64``) or via
    an environment variable named ``key_env`` (also base64). Keeping keys in the
    environment avoids persisting secrets in exported configurations.
    """
    enabled: bool = False
    algorithm: Literal["AES-256-GCM"] = "AES-256-GCM"
    key_b64: Optional[str] = None
    key_env: Optional[str] = None


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

class ScreenOutput(BaseModel):
    type: Literal["screen"] = "screen"
    enabled: bool = True
    encryption: Optional[EncryptionConfig] = None


class MqttOutput(BaseModel):
    type: Literal["mqtt"] = "mqtt"
    enabled: bool = False
    host: str = "broker.hivemq.com"
    port: int = 1883
    topic: str = "iot/sim/{sensor}"
    qos: int = 0
    retain: bool = False
    tls: bool = False
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    encryption: Optional[EncryptionConfig] = None


class KafkaOutput(BaseModel):
    type: Literal["kafka"] = "kafka"
    enabled: bool = False
    bootstrap_servers: str = "localhost:9092"
    topic: str = "iot-sim"
    key_field: Optional[str] = None
    encryption: Optional[EncryptionConfig] = None


class TcpJsonOutput(BaseModel):
    """Send JSON payloads (newline-delimited) via TCP to a host:port."""
    type: Literal["tcp_json"] = "tcp_json"
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 5050
    encryption: Optional[EncryptionConfig] = None


class FileOutput(BaseModel):
    """Append (or overwrite) each payload as a line to a local file."""
    type: Literal["file_output"] = "file_output"
    enabled: bool = True
    path: str = "/app/output/sensor.log"
    mode: Literal["append", "overwrite"] = "append"
    format: Literal["jsonl", "json_pretty"] = "jsonl"
    encryption: Optional[EncryptionConfig] = None


class HttpOutput(BaseModel):
    """POST/PUT each payload as JSON to an HTTP(S) endpoint (webhook).

    The single most common cloud-ingestion pattern: REST webhooks accepted by
    AWS API Gateway, Azure Event Grid, HTTP-triggered functions, Elasticsearch,
    Splunk HEC, generic collectors, etc.
    """
    type: Literal["http"] = "http"
    enabled: bool = False
    url: str = "http://localhost:9000/ingest"
    method: Literal["POST", "PUT"] = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    bearer_token: Optional[str] = None
    basic_user: Optional[str] = None
    basic_pass: Optional[str] = None
    timeout_sec: float = Field(5.0, gt=0.0, le=60.0)
    verify_tls: bool = True
    encryption: Optional[EncryptionConfig] = None


class AmqpOutput(BaseModel):
    """Publish each payload to an AMQP 0-9-1 broker (RabbitMQ)."""
    type: Literal["amqp"] = "amqp"
    enabled: bool = False
    url: str = "amqp://guest:guest@localhost:5672/"
    exchange: str = ""  # "" = default exchange
    routing_key: str = "iot.sim.{sensor}"
    encryption: Optional[EncryptionConfig] = None


class CoapOutput(BaseModel):
    """Send each payload to a CoAP server (RFC 7252), the classic protocol for
    constrained/low-power IoT devices over UDP."""
    type: Literal["coap"] = "coap"
    enabled: bool = False
    uri: str = "coap://localhost:5683/ingest"
    method: Literal["POST", "PUT"] = "POST"
    encryption: Optional[EncryptionConfig] = None


OutputConfig = Union[
    ScreenOutput,
    MqttOutput,
    KafkaOutput,
    TcpJsonOutput,
    FileOutput,
    HttpOutput,
    AmqpOutput,
    CoapOutput,
]


# ---------------------------------------------------------------------------
# Sensor
# ---------------------------------------------------------------------------

class AnomalyConfig(BaseModel):
    """Inject anomalies into numeric fields with a given probability.

    For each emitted sample, with probability ``probability``, a randomly-chosen
    numeric field is multiplied by a factor sampled uniformly from
    ``[min_factor, max_factor]``. Useful to test downstream alerting pipelines.
    """
    enabled: bool = False
    probability: float = Field(0.0, ge=0.0, le=1.0)
    min_factor: float = 1.5
    max_factor: float = 3.0


class SensorConfig(BaseModel):
    id: Optional[str] = None
    name: str
    interval_sec: float = Field(1.0, ge=0.05, le=3600)
    jitter_sec: float = Field(
        0.0, ge=0.0, le=60.0,
        description="Random extra delay in [0, jitter_sec) added to each interval.",
    )
    fields: List[FieldConfig] = Field(default_factory=list)
    outputs: List[OutputConfig] = Field(default_factory=lambda: [ScreenOutput()])
    anomaly: AnomalyConfig = Field(default_factory=AnomalyConfig)
    running: bool = False

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 80:
            raise ValueError("name must be 80 chars or fewer")
        return v


class SensorStatus(BaseModel):
    id: str
    name: str
    interval_sec: float
    jitter_sec: float = 0.0
    running: bool
    messages_sent: int
    errors: int = 0
    last_payload: Optional[dict] = None
    last_error: Optional[str] = None
    outputs_summary: List[str] = Field(default_factory=list)
    fields: List[FieldConfig] = Field(default_factory=list)
    outputs: List[OutputConfig] = Field(default_factory=list)
    anomaly: AnomalyConfig = Field(default_factory=AnomalyConfig)


class ImportRequest(BaseModel):
    """Body for ``POST /api/config/import``."""
    sensors: List[SensorConfig]
    replace: bool = False  # if true, delete existing sensors first
