"""Tests for optional AES-256-GCM payload encryption."""
import base64
import json

import pytest

from app.crypto import (
    EncryptionError,
    decrypt_envelope,
    encrypt_payload,
    generate_key_b64,
)
from app.models import EncryptionConfig


def test_roundtrip_key_b64():
    key = generate_key_b64()
    payload = {"temp": 22.5, "id": "abc"}
    text = json.dumps(payload)
    enc = EncryptionConfig(enabled=True, key_b64=key)
    env = encrypt_payload(payload, text, enc, aad="sensor-1")
    assert env["enc"] == "AES-256-GCM"
    assert set(env) == {"enc", "iv", "ct", "tag", "aad"}
    assert json.loads(decrypt_envelope(env, key)) == payload


def test_roundtrip_key_env(monkeypatch):
    key = generate_key_b64()
    monkeypatch.setenv("MY_KEY", key)
    enc = EncryptionConfig(enabled=True, key_env="MY_KEY")
    payload = {"x": 1}
    env = encrypt_payload(payload, json.dumps(payload), enc, aad="s")
    assert json.loads(decrypt_envelope(env, key)) == payload


def test_missing_env_key():
    enc = EncryptionConfig(enabled=True, key_env="DOES_NOT_EXIST")
    with pytest.raises(EncryptionError):
        encrypt_payload({}, "{}", enc)


def test_no_key_provided():
    enc = EncryptionConfig(enabled=True)
    with pytest.raises(EncryptionError):
        encrypt_payload({}, "{}", enc)


def test_wrong_key_length():
    short = base64.b64encode(b"tooshort").decode()
    enc = EncryptionConfig(enabled=True, key_b64=short)
    with pytest.raises(EncryptionError):
        encrypt_payload({}, "{}", enc)


def test_aad_is_authenticated():
    key = generate_key_b64()
    enc = EncryptionConfig(enabled=True, key_b64=key)
    env = encrypt_payload({"a": 1}, '{"a": 1}', enc, aad="sensor-1")
    env["aad"] = "tampered"
    with pytest.raises(Exception):  # noqa: B017 — GCM tag mismatch
        decrypt_envelope(env, key)
