"""Model validation tests."""
import pytest
from pydantic import ValidationError

from app.models import EnumField, SensorConfig


def test_enum_weights_length_must_match():
    with pytest.raises(ValidationError):
        EnumField(name="e", values=["a", "b"], weights=[1.0])


def test_enum_requires_values():
    with pytest.raises(ValidationError):
        EnumField(name="e", values=[])


def test_name_required_and_trimmed():
    with pytest.raises(ValidationError):
        SensorConfig(name="   ")
    cfg = SensorConfig(name="  padded  ")
    assert cfg.name == "padded"


def test_interval_bounds():
    with pytest.raises(ValidationError):
        SensorConfig(name="x", interval_sec=0.0)
    with pytest.raises(ValidationError):
        SensorConfig(name="x", interval_sec=99999)


def test_output_discriminated_union():
    cfg = SensorConfig(name="x", outputs=[
        {"type": "http", "url": "http://h/i"},
        {"type": "amqp", "routing_key": "k"},
        {"type": "coap", "uri": "coap://h/i"},
    ])
    assert [o.type for o in cfg.outputs] == ["http", "amqp", "coap"]
