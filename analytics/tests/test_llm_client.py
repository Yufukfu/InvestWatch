"""LLM config and the OpenAI-compatible client (analytics-llm-p0 task group 5). Only the local stub is called."""

from __future__ import annotations

import json
import logging
import time

import pytest

from llm_stub import Reply, closed_port_url
from investwatch_analytics.config import ConfigError, LlmSettings


def settings(base_url: str, **kw) -> LlmSettings:
    env = {"LLM_BASE_URL": base_url, "LLM_MODEL": "gemma3:4b", **kw}
    return LlmSettings.from_env(env)


def all_log_text(caplog) -> str:
    return "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)


# ---- configuration ------------------------------------------------------------------------------


def test_llm_disabled_by_default():
    s = LlmSettings.from_env({})
    assert not s.enabled and s.base_url == ""


def test_llm_disabled_when_base_url_blank():
    assert not LlmSettings.from_env({"LLM_BASE_URL": "   ", "LLM_MODEL": "x"}).enabled


def test_defaults():
    s = settings("http://127.0.0.1:1/v1")
    assert s.enabled and s.model == "gemma3:4b" and s.api_key == ""
    assert (s.timeout_s, s.doc_budget_s, s.chunk_chars, s.max_chunks) == (20, 40, 9000, 4)
    assert (s.cache_ttl_s, s.breaker_failures, s.breaker_cooldown_s) == (604800, 3, 60)


def test_model_missing_is_a_config_error():
    with pytest.raises(ConfigError, match="LLM_MODEL"):
        LlmSettings.from_env({"LLM_BASE_URL": "http://127.0.0.1:1/v1", "LLM_MODEL": " "})


@pytest.mark.parametrize("key, value", [
    ("LLM_TIMEOUT_S", "0"), ("LLM_TIMEOUT_S", "abc"), ("LLM_TIMEOUT_S", "nan"), ("LLM_DOC_BUDGET_S", "-1"),
    ("LLM_CHUNK_CHARS", "1.5"), ("LLM_MAX_CHUNKS", "0"), ("LLM_CACHE_TTL_S", "x"),
    ("LLM_BREAKER_FAILURES", "0"), ("LLM_BREAKER_COOLDOWN_S", "inf"),
])
def test_bad_limit_names_the_variable(key, value):
    with pytest.raises(ConfigError, match=key):
        settings("http://127.0.0.1:1/v1", **{key: value})


def test_limits_are_ignored_when_disabled():
    assert not LlmSettings.from_env({"LLM_TIMEOUT_S": "abc"}).enabled


def test_budget_must_stay_below_claim_idle():
    env = {"LLM_BASE_URL": "http://127.0.0.1:1/v1", "LLM_MODEL": "m", "LLM_DOC_BUDGET_S": "90"}
    with pytest.raises(ConfigError, match="LLM_DOC_BUDGET_S"):
        LlmSettings.from_env(env, claim_min_idle_ms=60000)
    env["LLM_DOC_BUDGET_S"] = "60"
    with pytest.raises(ConfigError, match="LLM_DOC_BUDGET_S"):
        LlmSettings.from_env(env, claim_min_idle_ms=60000)
    env["LLM_DOC_BUDGET_S"] = "59.5"
    assert LlmSettings.from_env(env, claim_min_idle_ms=60000).doc_budget_s == 59.5


def test_key_never_in_config_errors():
    with pytest.raises(ConfigError) as exc:
        LlmSettings.from_env({"LLM_BASE_URL": "http://127.0.0.1:1/v1", "LLM_MODEL": "",
                              "LLM_API_KEY": "sk-test-123"})
    assert "sk-test-123" not in str(exc.value)


def test_settings_repr_hides_the_key():
    s = settings("http://127.0.0.1:1/v1", LLM_API_KEY="sk-test-123")
    assert "sk-test-123" not in repr(s) and s.api_key == "sk-test-123"


def test_mode_hosted_or_local():
    assert settings("http://ollama:11434/v1").mode == "local"
    assert settings("http://127.0.0.1:11434/v1").mode == "local"
    assert settings("https://api.example.com/v1").mode == "hosted"
    assert LlmSettings.from_env({}).mode == "disabled"


# ---- client --------------------------------------------------------------------------------------


def client_for(stub_or_url, **kw):
    from investwatch_analytics.llm.client import ChatClient

    url = stub_or_url if isinstance(stub_or_url, str) else stub_or_url.base_url
    return ChatClient(settings(url, **kw))


def test_request_shape(stub_llm):
    stub_llm.script.append(Reply.results())
    client_for(stub_llm).complete("SYSTEM", "<document>\nx\n</document>")
    [req] = stub_llm.requests
    assert req["path"] == "/v1/chat/completions"
    body = req["body"]
    assert body["model"] == "gemma3:4b" and body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["messages"][1]["content"] == "<document>\nx\n</document>"
    assert set(body) == {"model", "messages", "temperature", "response_format"}


def test_no_authorization_without_key(stub_llm):
    client_for(stub_llm).complete("s", "u")
    assert "Authorization" not in stub_llm.requests[0]["headers"]


def test_bearer_key_when_set(stub_llm):
    client_for(stub_llm, LLM_API_KEY="sk-test-123").complete("s", "u")
    assert stub_llm.requests[0]["headers"]["Authorization"] == "Bearer sk-test-123"


def test_returns_parsed_content(stub_llm):
    item = {"rule_id": "R17", "result": "fail", "evidence_quote": "Działamy pod nadzorem KNF", "explanation": "x"}
    stub_llm.script.append(Reply.results(item))
    assert client_for(stub_llm).complete("s", "u") == {"results": [item]}


@pytest.mark.parametrize("reply, reason", [
    (Reply(status=500), "llm_unavailable"),
    (Reply(status=503), "llm_unavailable"),
    (Reply(status=429), "llm_unavailable"),
    (Reply(status=401), "llm_unavailable"),
    (Reply(status=403), "llm_unavailable"),
    (Reply(status=404), "llm_unavailable"),
    (Reply(close=True), "llm_unavailable"),
])
def test_unavailable(stub_llm, reply, reason):
    from investwatch_analytics.llm.client import LlmUnavailable

    stub_llm.script.append(reply)
    with pytest.raises(LlmUnavailable) as exc:
        client_for(stub_llm).complete("s", "u")
    assert exc.value.reason == reason


def test_connection_refused_is_unavailable():
    from investwatch_analytics.llm.client import LlmUnavailable

    with pytest.raises(LlmUnavailable) as exc:
        client_for(closed_port_url()).complete("s", "u")
    assert exc.value.reason == "llm_unavailable"


def test_timeout(stub_llm):
    from investwatch_analytics.llm.client import LlmUnavailable

    stub_llm.script.append(Reply(sleep_s=3))
    client = client_for(stub_llm, LLM_TIMEOUT_S="0.5")
    start = time.perf_counter()
    with pytest.raises(LlmUnavailable) as exc:
        client.complete("s", "u")
    assert exc.value.reason == "llm_timeout"
    assert time.perf_counter() - start < 0.5 + 1


def test_per_call_timeout_overrides_setting(stub_llm):
    from investwatch_analytics.llm.client import LlmUnavailable

    stub_llm.script.append(Reply(sleep_s=2))
    client = client_for(stub_llm, LLM_TIMEOUT_S="20")
    start = time.perf_counter()
    with pytest.raises(LlmUnavailable):
        client.complete("s", "u", timeout_s=0.3)
    assert time.perf_counter() - start < 1.5


@pytest.mark.parametrize("reply", [
    Reply(content='{"results": [{"rule_id": "R17", "result": "fail"'),     # truncated JSON
    Reply(content='[{"rule_id": "R17", "result": "fail"}]'),               # array, not an object
    Reply(content='{"verdicts": []}'),                                      # no results list
    Reply(content='{"results": "R17 fail"}'),                               # results not a list
    Reply(content=None),                                                    # no content
    Reply(body=b"<html>gateway</html>"),                                    # not chat-completions JSON
    Reply(body=b'{"choices": []}'),                                         # no choice
    Reply(body=b'{"choices": [{"message": {"content": 5}}]}'),              # content not a string
])
def test_malformed(stub_llm, reply):
    from investwatch_analytics.llm.client import LlmMalformed

    stub_llm.script.append(reply)
    with pytest.raises(LlmMalformed) as exc:
        client_for(stub_llm).complete("s", "u")
    assert exc.value.reason == "llm_malformed"


def test_logs_never_carry_key_or_bodies(stub_llm, caplog):
    caplog.set_level(logging.DEBUG)
    stub_llm.script.append(Reply.results({"rule_id": "R17", "result": "fail",
                                          "evidence_quote": "ODPOWIEDZ-MODELU", "explanation": "x"}))
    stub_llm.script.append(Reply(status=401, body=b'{"error": "bad key sk-test-123"}'))
    c = client_for(stub_llm, LLM_API_KEY="sk-test-123")
    c.complete("SYSTEM", "Zarabiaj 18% rocznie")
    with pytest.raises(Exception):
        c.complete("SYSTEM", "Zarabiaj 18% rocznie")
    text = all_log_text(caplog)
    assert "sk-test-123" not in text and "Zarabiaj 18% rocznie" not in text and "ODPOWIEDZ-MODELU" not in text
    assert "127.0.0.1" in text and "gemma3:4b" in text  # host and model are logged


def test_error_messages_never_carry_the_key(stub_llm):
    from investwatch_analytics.llm.client import LlmUnavailable

    stub_llm.script.append(Reply(status=401, body=b'{"error": "bad key sk-test-123"}'))
    with pytest.raises(LlmUnavailable) as exc:
        client_for(stub_llm, LLM_API_KEY="sk-test-123").complete("s", "u")
    assert "sk-test-123" not in str(exc.value) and "sk-test-123" not in repr(exc.value)


def test_base_url_with_trailing_slash(stub_llm):
    from investwatch_analytics.llm.client import ChatClient

    ChatClient(settings(stub_llm.base_url + "/")).complete("s", "u")
    assert stub_llm.requests[0]["path"] == "/v1/chat/completions"


def test_network_guard_blocks_non_local_hosts():
    import httpx

    with pytest.raises(AssertionError, match="non-local host"):
        httpx.Client().get("https://llm.invalid/v1/models")  # reserved TLD: never resolves, never a real LLM


def test_stub_records_json_body(stub_llm):
    client_for(stub_llm).complete("s", "u")
    assert json.dumps(stub_llm.requests[0]["body"])


# ---- group 5 review fixes ------------------------------------------------------------------------


def _drip_server(body: bytes, delay: float, *, headers_slow: bool = False):
    """Raw-socket server answering one request, trickling the body one byte every `delay` seconds."""
    import socket
    import threading

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    from llm_stub import register_port

    register_port(port)

    def serve():
        conn, _ = srv.accept()
        conn.recv(65536)
        head = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n".encode()
        try:
            conn.sendall(head)
            for b in body:
                conn.sendall(bytes([b]))
                time.sleep(delay)
        except OSError:
            pass
        finally:
            conn.close()
            srv.close()

    threading.Thread(target=serve, daemon=True).start()
    return f"http://127.0.0.1:{port}/v1"


def test_slow_drip_body_is_bounded_by_the_total_deadline():
    from investwatch_analytics.llm.client import LlmUnavailable

    content = json.dumps({"results": []})
    body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
    url = _drip_server(body, 0.2)
    client = client_for(url, LLM_TIMEOUT_S="1")  # built first: creating the SSL context is not part of the call
    start = time.perf_counter()
    with pytest.raises(LlmUnavailable) as exc:
        client.complete("s", "u")
    assert exc.value.reason == "llm_timeout" and time.perf_counter() - start < 1 + 1


def test_oversized_response_is_malformed(stub_llm):
    from investwatch_analytics.llm.client import MAX_RESPONSE_BYTES, LlmMalformed

    envelope = {"choices": [{"message": {"content": '{"results": []}'}}], "pad": "x" * (MAX_RESPONSE_BYTES + 10)}
    stub_llm.script.append(Reply(body=json.dumps(envelope).encode()))  # valid JSON: only the size cap rejects it
    with pytest.raises(LlmMalformed):
        client_for(stub_llm).complete("s", "u")


@pytest.mark.parametrize("url", [
    "api.example.com/v1", "ftp://api.example.com/v1", "http:///v1",
    "http://user:pw@127.0.0.1:1/v1", "https://api.example.com/v1?key=x", "https://api.example.com/v1#x",
])
def test_bad_base_url_is_a_config_error(url):
    with pytest.raises(ConfigError, match="LLM_BASE_URL") as exc:
        LlmSettings.from_env({"LLM_BASE_URL": url, "LLM_MODEL": "m"})
    assert "pw" not in str(exc.value) and "key=x" not in str(exc.value)


def test_key_over_plain_http_to_a_remote_host_is_refused():
    with pytest.raises(ConfigError, match="LLM_BASE_URL"):
        LlmSettings.from_env({"LLM_BASE_URL": "http://gpu-box.lan:11434/v1", "LLM_MODEL": "m", "LLM_API_KEY": "k"})
    # local Ollama over http, or a remote http endpoint without a key, stays allowed
    assert LlmSettings.from_env({"LLM_BASE_URL": "http://ollama:11434/v1", "LLM_MODEL": "m", "LLM_API_KEY": "ollama"}).enabled
    assert LlmSettings.from_env({"LLM_BASE_URL": "http://gpu-box.lan:11434/v1", "LLM_MODEL": "m"}).enabled


def test_proxy_environment_is_ignored(stub_llm, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://10.255.255.1:3128")
    monkeypatch.setenv("http_proxy", "http://10.255.255.1:3128")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    client_for(stub_llm, LLM_TIMEOUT_S="2").complete("s", "u")
    assert len(stub_llm.requests) == 1


def test_network_guard_blocks_loopback_ports_that_are_not_a_stub():
    import httpx

    with pytest.raises(AssertionError, match="not a test stub"):
        httpx.Client().get("http://127.0.0.1:11434/v1/models")  # a developer's real local Ollama


# ---- hosted Gemma 4 (task 12.4) and the embeddings-session review holes ----------------------------------


def test_leading_thought_block_is_stripped(stub_llm):
    content = '<thought>*   Input: a document.\n*   Plan: answer.</thought>\n{"results": []}'
    stub_llm.script.append(Reply(content=content))
    assert client_for(stub_llm).complete("s", "u") == {"results": []}


def test_thought_block_with_fenced_json(stub_llm):
    stub_llm.script.append(Reply(content='<thought>x</thought>\n```json\n{"results": []}\n```'))
    assert client_for(stub_llm).complete("s", "u") == {"results": []}


@pytest.mark.parametrize("content", [
    '<thought>never closed {"results": []}',          # unterminated thought: not an answer
    '<thought> {"results": []}',                       # unterminated, even when JSON follows
    'Sure! {"results": []}',                           # prose before the object is still malformed
])
def test_other_wrappers_stay_malformed(stub_llm, content):
    from investwatch_analytics.llm.client import LlmMalformed

    stub_llm.script.append(Reply(content=content))
    with pytest.raises(LlmMalformed):
        client_for(stub_llm).complete("s", "u")


def test_deeply_nested_json_is_malformed_not_a_crash(stub_llm):
    from investwatch_analytics.llm.client import LlmMalformed

    deep = "[" * 100_000 + "]" * 100_000
    stub_llm.script.append(Reply(content=deep))
    with pytest.raises(LlmMalformed):
        client_for(stub_llm).complete("s", "u")


def test_deeply_nested_envelope_is_malformed(stub_llm):
    from investwatch_analytics.llm.client import LlmMalformed

    stub_llm.script.append(Reply(body=b"[" * 100_000 + b"]" * 100_000))
    with pytest.raises(LlmMalformed):
        client_for(stub_llm).complete("s", "u")


@pytest.mark.parametrize("url", [
    "http://ollama:99999/v1", "http://ollama:abc/v1", "http://ollama:11434/v 1", "http://oll ama:11434/v1",
    "http://ollama:11434/\tv1", "http://ollama:11434/v1\x00",  # a trailing newline is stripped on purpose
])
def test_bad_port_or_whitespace_in_base_url(url):
    with pytest.raises(ConfigError, match="LLM_BASE_URL"):
        LlmSettings.from_env({"LLM_BASE_URL": url, "LLM_MODEL": "m"})


def test_valid_port_is_accepted():
    assert LlmSettings.from_env({"LLM_BASE_URL": "http://ollama:11434/v1", "LLM_MODEL": "m"}).enabled


def test_hosted_gemma_limits_pass_the_budget_check():
    """ADR 0317: LLM_TIMEOUT_S=45, LLM_DOC_BUDGET_S=50 with CLAIM_MIN_IDLE_MS=90000 must start the worker."""
    s = LlmSettings.from_env({"LLM_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
                              "LLM_MODEL": "gemma-4-31b-it", "LLM_API_KEY": "k", "LLM_TIMEOUT_S": "45",
                              "LLM_DOC_BUDGET_S": "50"}, claim_min_idle_ms=90000)
    assert (s.timeout_s, s.doc_budget_s, s.mode) == (45, 50, "hosted")
