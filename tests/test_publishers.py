"""Tests for output dispatch: screen, file, HTTP webhook, encryption, errors."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.crypto import decrypt_envelope, generate_key_b64
from app.models import (
    EncryptionConfig,
    FileOutput,
    HttpOutput,
    ScreenOutput,
    TcpJsonOutput,
)
from app.publishers import PublisherHub

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def http_server():
    received = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            received.append({
                "body": self.rfile.read(n).decode(),
                "auth": self.headers.get("Authorization"),
            })
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}/ingest", received
    srv.shutdown()


async def test_screen_only():
    hub = PublisherHub()
    targets = await hub.dispatch("s1", [ScreenOutput()], {"a": 1})
    assert targets == ["screen"]
    assert hub.total_messages == 1
    await hub.close()


async def test_file_output(tmp_path):
    hub = PublisherHub()
    path = tmp_path / "out.jsonl"
    out = FileOutput(enabled=True, path=str(path), mode="append", format="jsonl")
    await hub.dispatch("s1", [out], {"a": 1})
    await hub.dispatch("s1", [out], {"a": 2})
    lines = path.read_text().strip().splitlines()
    assert [json.loads(x)["a"] for x in lines] == [1, 2]
    await hub.close()


async def test_file_output_encrypted(tmp_path):
    hub = PublisherHub()
    key = generate_key_b64()
    path = tmp_path / "enc.jsonl"
    out = FileOutput(
        enabled=True, path=str(path),
        encryption=EncryptionConfig(enabled=True, key_b64=key),
    )
    await hub.dispatch("sensor-x", [out], {"secret": 42})
    envelope = json.loads(path.read_text().strip())
    assert envelope["enc"] == "AES-256-GCM"
    assert json.loads(decrypt_envelope(envelope, key)) == {"secret": 42}
    await hub.close()


async def test_http_webhook(http_server):
    url, received = http_server
    hub = PublisherHub()
    out = HttpOutput(enabled=True, url=url, method="POST", bearer_token="tok123")
    targets = await hub.dispatch("s1", [out], {"v": 99})
    assert targets[0].startswith("http(POST")
    assert len(received) == 1
    assert json.loads(received[0]["body"]) == {"v": 99}
    assert received[0]["auth"] == "Bearer tok123"
    await hub.close()


async def test_error_isolation():
    """A failing output must not stop the others; it is tagged !ERR."""
    hub = PublisherHub()
    outs = [
        ScreenOutput(),
        TcpJsonOutput(enabled=True, host="127.0.0.1", port=1),  # nothing listening
    ]
    targets = await hub.dispatch("s1", outs, {"a": 1})
    assert targets[0] == "screen"
    assert targets[1] == "tcp_json!ERR"
    assert hub.total_errors == 1
    await hub.close()


async def test_disabled_output_skipped():
    hub = PublisherHub()
    targets = await hub.dispatch("s1", [ScreenOutput(enabled=False)], {"a": 1})
    assert targets == []
    await hub.close()
