"""Optional payload encryption helpers (AES-256-GCM envelopes)."""
from __future__ import annotations

import base64
import os
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .models import EncryptionConfig


class EncryptionError(RuntimeError):
    """Raised when an encryption key is missing or malformed."""


def _resolve_key(cfg: EncryptionConfig) -> bytes:
    """Return the raw 32-byte AES-256 key from config or environment."""
    raw_b64: Optional[str] = None
    if cfg.key_env:
        raw_b64 = os.getenv(cfg.key_env)
        if not raw_b64:
            raise EncryptionError(
                f"encryption key env var '{cfg.key_env}' is not set"
            )
    elif cfg.key_b64:
        raw_b64 = cfg.key_b64
    else:
        raise EncryptionError("encryption enabled but no key_b64/key_env provided")

    try:
        key = base64.b64decode(raw_b64, validate=True)
    except Exception as e:  # noqa: BLE001
        raise EncryptionError(f"encryption key is not valid base64: {e}") from e
    if len(key) != 32:
        raise EncryptionError(
            f"AES-256-GCM requires a 32-byte key, got {len(key)} bytes"
        )
    return key


def generate_key_b64() -> str:
    """Generate a fresh base64-encoded 256-bit key (helper for docs/tests)."""
    return base64.b64encode(os.urandom(32)).decode("ascii")


def encrypt_payload(
    payload: Dict[str, Any],
    text: str,
    cfg: EncryptionConfig,
    aad: str = "",
) -> Dict[str, Any]:
    """Encrypt ``text`` (the JSON serialization of ``payload``) into an envelope.

    Returns a JSON-serializable dict. ``aad`` (additional authenticated data,
    typically the sensor name) is authenticated but not encrypted.
    """
    key = _resolve_key(cfg)
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    aad_bytes = aad.encode("utf-8")
    combined = aesgcm.encrypt(iv, text.encode("utf-8"), aad_bytes)
    # AESGCM appends the 16-byte tag to the ciphertext.
    ct, tag = combined[:-16], combined[-16:]
    return {
        "enc": cfg.algorithm,
        "iv": base64.b64encode(iv).decode("ascii"),
        "ct": base64.b64encode(ct).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
        "aad": aad,
    }


def decrypt_envelope(envelope: Dict[str, Any], key_b64: str) -> str:
    """Inverse of :func:`encrypt_payload` — returns the original JSON string.

    Provided so tests (and downstream consumers) can round-trip the envelope.
    """
    key = base64.b64decode(key_b64, validate=True)
    iv = base64.b64decode(envelope["iv"])
    ct = base64.b64decode(envelope["ct"])
    tag = base64.b64decode(envelope["tag"])
    aad = (envelope.get("aad") or "").encode("utf-8")
    aesgcm = AESGCM(key)
    plain = aesgcm.decrypt(iv, ct + tag, aad)
    return plain.decode("utf-8")
