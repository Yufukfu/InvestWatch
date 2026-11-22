"""Embeddings client, vector validation and the stub server (analytics-embeddings task group 2).

Only the local stub (`llm_stub.StubLLM`, answering raw `/v1/embeddings` bodies) is called.
"""

from __future__ import annotations

import json
import logging
import math
import time

import numpy as np
import pytest

from llm_stub import Reply, closed_port_url
from investwatch_analytics.config import EmbedSettings
from investwatch_analytics.embeddings.client import EmbedClient, EmbedMalformed, EmbedUnavailable


def body(*vectors) -> bytes:
    return json.dumps({"object": "list", "model": "bge-m3",
                       "data": [{"object": "embedding", "index": i, "embedding": list(v)}
                                for i, v in enumerate(vectors)]}).encode()


def vec(dim: int = 8, value: float = 1.0) -> list[float]:
    return [value] * dim


def client(base_url: str, **env) -> EmbedClient:
    s = EmbedSettings.from_env({"EMBED_BASE_URL": base_url, "EMBED_DIM": "8", **env})
    return EmbedClient(s)


def log_text(caplog) -> str:
    return "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)


# ---- request shape ----------------------------------------------------------------------------


def test_request_shape(stub_llm):
    stub_llm.default = Reply(body=body(vec()))
    client(stub_llm.base_url).embed("Zarabiaj 18% rocznie")
    [req] = stub_llm.requests
    assert req["path"] == "/v1/embeddings"
    assert req["body"] == {"model": "bge-m3", "input": ["Zarabiaj 18% rocznie"]}
    assert "authorization" not in {k.lower() for k in req["headers"]}


def test_key_sent_as_bearer(stub_llm):
    stub_llm.default = Reply(body=body(vec()))
    client(stub_llm.base_url, EMBED_API_KEY="sk-emb-123").embed("x")
    headers = {k.lower(): v for k, v in stub_llm.requests[0]["headers"].items()}
    assert headers["authorization"] == "Bearer sk-emb-123"


def test_lone_surrogate_in_scraped_text(stub_llm):
    stub_llm.default = Reply(body=body(vec()))
    text = "Zysk " + chr(0xD800) + " 20%"
    client(stub_llm.base_url).embed(text)
    assert stub_llm.requests[0]["body"]["input"] == [text]


def test_no_compression_requested(stub_llm):
    stub_llm.default = Reply(body=body(vec()))
    client(stub_llm.base_url).embed("x")
    headers = {k.lower(): v for k, v in stub_llm.requests[0]["headers"].items()}
    assert headers["accept-encoding"] == "identity"


def test_long_text_is_cut(stub_llm):
    stub_llm.default = Reply(body=body(vec()))
    text = "a" * 19_999 + "b"
    client(stub_llm.base_url, EMBED_MAX_CHARS="4000").embed(text)
    sent = stub_llm.requests[0]["body"]["input"][0]
    assert sent == text[:4000] and len(sent) == 4000


def test_empty_text_never_sent(stub_llm):
    with pytest.raises(ValueError):
        client(stub_llm.base_url).embed("   ")
    assert stub_llm.requests == []


# ---- vector validation ------------------------------------------------------------------------


def test_valid_vector_is_l2_normalized_float32(stub_llm):
    stub_llm.default = Reply(body=body([3.0, 4.0] + [0.0] * 6))
    v = client(stub_llm.base_url).embed("x")
    assert v.dtype == np.float32 and v.shape == (8,)
    assert math.isclose(float(np.linalg.norm(v)), 1.0, rel_tol=1e-6)
    assert math.isclose(float(v[0]), 0.6, rel_tol=1e-6) and math.isclose(float(v[1]), 0.8, rel_tol=1e-6)


def test_wrong_vector_size(stub_llm, caplog):
    stub_llm.default = Reply(body=body(vec(6)))
    with caplog.at_level(logging.WARNING), pytest.raises(EmbedMalformed) as exc:
        client(stub_llm.base_url).embed("x")
    assert "6" in str(exc.value) and "8" in str(exc.value)
    assert exc.value.reason == "embed_malformed"
    assert any(getattr(r, "reason", None) == "embed_malformed" for r in caplog.records)


@pytest.mark.parametrize("payload", [
    body([float("nan")] + [1.0] * 7),
    json.dumps({"data": [{"embedding": [1.0] * 7 + ["x"]}]}).encode(),
    json.dumps({"data": [{"embedding": [1.0] * 7 + [True]}]}).encode(),
    json.dumps({"data": [{"embedding": [1e309] * 8}]}).encode(),
    body(vec(8, 0.0)),
    json.dumps({"error": "model not found"}).encode(),
    json.dumps({"data": []}).encode(),
    json.dumps({"data": [{"embedding": "nope"}]}).encode(),
    json.dumps({"data": [{"embedding": 5}]}).encode(),
    json.dumps({"data": [{"embedding": [1e308] * 8}]}).encode(),
    json.dumps({"data": [{"embedding": [10**400] * 8}]}).encode(),
    b"[" * 200_000,
    json.dumps([1, 2, 3]).encode(),
    b"<html>not json</html>",
], ids=["nan", "string", "bool", "inf", "zeros", "error", "empty-data", "not-list", "number", "overflow", "huge-int", "deep-nesting", "array", "html"])
def test_malformed_answers(stub_llm, payload):
    stub_llm.default = Reply(body=payload)
    with pytest.raises(EmbedMalformed):
        client(stub_llm.base_url).embed("x")


def test_oversized_response_is_malformed(stub_llm):
    # A valid vector padded past the cap: only the size limit can reject it.
    padded = json.dumps({"data": [{"embedding": vec()}], "pad": "x" * 1_100_000}).encode()
    stub_llm.default = Reply(body=padded)
    with pytest.raises(EmbedMalformed, match="too large"):
        client(stub_llm.base_url).embed("x")


def test_valid_padded_response_under_cap_is_accepted(stub_llm):
    stub_llm.default = Reply(body=json.dumps({"data": [{"embedding": vec()}], "pad": "x" * 900_000}).encode())
    assert client(stub_llm.base_url).embed("x").shape == (8,)


# ---- unavailable ------------------------------------------------------------------------------


def test_connection_refused():
    with pytest.raises(EmbedUnavailable) as exc:
        client(closed_port_url()).embed("x")
    assert exc.value.reason == "embed_unavailable"


@pytest.mark.parametrize("status", [404, 429, 401, 403, 500, 503])
def test_http_errors_are_unavailable(stub_llm, status):
    stub_llm.default = Reply(status=status, body=b'{"error": "x"}')
    with pytest.raises(EmbedUnavailable) as exc:
        client(stub_llm.base_url).embed("x")
    assert exc.value.status == status and exc.value.reason == "embed_unavailable"


def test_slow_embedder_times_out(stub_llm):
    stub_llm.default = Reply(body=body(vec()), sleep_s=3)
    c = client(stub_llm.base_url, EMBED_TIMEOUT_S="0.5")  # built first: SSL context setup is not the call
    started = time.monotonic()
    with pytest.raises(EmbedUnavailable) as exc:
        c.embed("x")
    assert time.monotonic() - started < 1.5
    assert exc.value.reason == "embed_timeout"


def test_closed_connection(stub_llm):
    stub_llm.default = Reply(close=True)
    with pytest.raises(EmbedUnavailable):
        client(stub_llm.base_url).embed("x")


class _Raw:
    """A loopback server with one custom handler (trickled body, redirect); registered with the test guard."""

    def __init__(self, handler):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading

        from llm_stub import register_port

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                return

            def do_POST(self):  # noqa: N802
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                handler(self)

        self.hits = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        register_port(self.server.server_address[1])
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def test_trickled_body_hits_the_total_deadline():
    payload = body(vec())

    def trickle(h):
        h.send_response(200)
        h.send_header("Content-Length", str(len(payload)))
        h.end_headers()
        for b in payload:  # one byte every 0.1 s: each read is fast, the whole body is not
            try:
                h.wfile.write(bytes([b]))
                h.wfile.flush()
            except OSError:
                return
            time.sleep(0.1)

    srv = _Raw(trickle)
    try:
        c = client(srv.base_url, EMBED_TIMEOUT_S="1")
        started = time.monotonic()
        with pytest.raises(EmbedUnavailable) as exc:
            c.embed("x")
        assert exc.value.reason == "embed_timeout" and time.monotonic() - started < 3
    finally:
        srv.stop()


def test_no_redirect_followed(stub_llm):
    def redirect(h):
        h.send_response(307)
        h.send_header("Location", stub_llm.base_url + "/embeddings")
        h.send_header("Content-Length", "0")
        h.end_headers()

    stub_llm.default = Reply(body=body(vec()))
    srv = _Raw(redirect)
    try:
        with pytest.raises(EmbedUnavailable) as exc:
            client(srv.base_url).embed("x")
        assert exc.value.status == 307 and stub_llm.requests == []
    finally:
        srv.stop()


# ---- logging ----------------------------------------------------------------------------------


def test_bodies_and_key_stay_out_of_logs(stub_llm, caplog):
    stub_llm.script = [Reply(body=body([0.123456] * 8)), Reply(status=401, body=b'{"error":"Zarabiaj"}')]
    c = client(stub_llm.base_url, EMBED_API_KEY="sk-emb-123")
    with caplog.at_level(logging.DEBUG):
        c.embed("Zarabiaj 18% rocznie")
        with pytest.raises(EmbedUnavailable):
            c.embed("Zarabiaj 18% rocznie")
    text = log_text(caplog)
    assert "Zarabiaj" not in text and "sk-emb-123" not in text and "0.123456" not in text
    assert "embed call" in text


# ---- test guard -------------------------------------------------------------------------------


def test_guard_blocks_a_real_endpoint():
    """The conftest guard fails any test whose embedder targets a non-stub host."""
    with pytest.raises(AssertionError, match="non-local host"):
        client("http://ollama:11434/v1").embed("x")
