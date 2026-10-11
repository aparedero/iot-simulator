"""Shared pytest fixtures. Disables the TCP/CoAP listeners during tests."""
import os

os.environ.setdefault("LISTEN_PORT", "0")  # no TCP listener in tests
os.environ.setdefault("COAP_LISTEN_PORT", "0")  # no CoAP listener in tests

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        # start from a clean slate for every test
        c.delete("/api/sensors")
        yield c
        c.delete("/api/sensors")


@pytest.fixture(autouse=True)
def _file_sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("IOTSIM_FILE_FIELD_ROOT", str(tmp_path))
    monkeypatch.setenv("IOTSIM_FILE_OUTPUT_ROOT", str(tmp_path))
