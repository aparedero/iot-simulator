"""Shared pytest fixtures. Disables the TCP listener during tests."""
import os

os.environ.setdefault("LISTEN_PORT", "0")  # no TCP listener in tests

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
