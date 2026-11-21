"""EMBED_* / GATE_* / NEARDUP_* settings (analytics-embeddings task group 1)."""

from __future__ import annotations

import pytest

from investwatch_analytics.config import ConfigError, EmbedSettings, GateSettings, NearDupSettings

URL = "http://ollama:11434/v1"


# ---- embeddings -------------------------------------------------------------------------------


def test_embeddings_disabled_by_default():
    s = EmbedSettings.from_env({})
    assert not s.enabled and s.mode == "disabled"


def test_blank_base_url_disables():
    assert not EmbedSettings.from_env({"EMBED_BASE_URL": "  "}).enabled


def test_defaults():
    s = EmbedSettings.from_env({"EMBED_BASE_URL": URL})
    assert s.enabled and s.model == "bge-m3" and s.api_key == ""
    assert (s.dim, s.timeout_s, s.max_chars, s.cache_ttl_s) == (1024, 5, 4000, 604800)
    assert (s.breaker_failures, s.breaker_cooldown_s) == (3, 60)


def test_mode_local_and_remote():
    assert EmbedSettings.from_env({"EMBED_BASE_URL": URL}).mode == "local"
    assert EmbedSettings.from_env({"EMBED_BASE_URL": "http://127.0.0.1:9/v1"}).mode == "local"
    assert EmbedSettings.from_env({"EMBED_BASE_URL": "http://tei.lan:8080/v1"}).mode == "remote"


def test_empty_model_is_an_error():
    with pytest.raises(ConfigError, match="EMBED_MODEL"):
        EmbedSettings.from_env({"EMBED_BASE_URL": URL, "EMBED_MODEL": ""})


def test_blank_model_is_an_error():
    with pytest.raises(ConfigError, match="EMBED_MODEL"):
        EmbedSettings.from_env({"EMBED_BASE_URL": URL, "EMBED_MODEL": "   "})


@pytest.mark.parametrize("key,value", [
    ("EMBED_DIM", "abc"), ("EMBED_DIM", "0"), ("EMBED_DIM", "1.5"), ("EMBED_TIMEOUT_S", "0"),
    ("EMBED_TIMEOUT_S", "-1"), ("EMBED_TIMEOUT_S", "nan"), ("EMBED_MAX_CHARS", "0"),
    ("EMBED_CACHE_TTL_S", "x"), ("EMBED_BREAKER_FAILURES", "0"), ("EMBED_BREAKER_COOLDOWN_S", "0"),
])
def test_bad_numbers_name_the_variable(key, value):
    with pytest.raises(ConfigError, match=key):
        EmbedSettings.from_env({"EMBED_BASE_URL": URL, key: value})


def test_numbers_not_checked_when_disabled():
    assert not EmbedSettings.from_env({"EMBED_DIM": "abc"}).enabled


@pytest.mark.parametrize("url", ["ftp://ollama/v1", "ollama:11434", "http://user:pw@ollama/v1",
                                 "http://ollama/v1?key=x", "http://ollama/v1#f"])
def test_bad_base_url(url):
    with pytest.raises(ConfigError, match="EMBED_BASE_URL") as exc:
        EmbedSettings.from_env({"EMBED_BASE_URL": url})
    assert "pw" not in str(exc.value) and "key=x" not in str(exc.value)


def test_key_over_plain_http_to_remote_host_rejected():
    with pytest.raises(ConfigError, match="https"):
        EmbedSettings.from_env({"EMBED_BASE_URL": "http://tei.lan/v1", "EMBED_API_KEY": "sk-emb-123"})


def test_key_never_in_repr():
    s = EmbedSettings.from_env({"EMBED_BASE_URL": URL, "EMBED_API_KEY": "sk-emb-123"})
    assert s.api_key == "sk-emb-123" and "sk-emb-123" not in repr(s)


def test_key_never_in_url_error():
    with pytest.raises(ConfigError) as exc:
        EmbedSettings.from_env({"EMBED_BASE_URL": "http://tei.lan/v1", "EMBED_API_KEY": "sk-emb-123"})
    assert "sk-emb-123" not in str(exc.value)


def test_key_over_https_to_remote_host_accepted():
    s = EmbedSettings.from_env({"EMBED_BASE_URL": "https://tei.lan/v1", "EMBED_API_KEY": "k"})
    assert s.enabled and s.mode == "remote"


def test_key_over_plain_http_to_local_host_accepted():
    assert EmbedSettings.from_env({"EMBED_BASE_URL": URL, "EMBED_API_KEY": "k"}).mode == "local"


@pytest.mark.parametrize("url", ["http://ollama:99999/v1", "http://ollama:abc/v1", "http://ollama/v1 x"])
def test_bad_port_or_whitespace_rejected_at_startup(url):
    with pytest.raises(ConfigError, match="EMBED_BASE_URL"):
        EmbedSettings.from_env({"EMBED_BASE_URL": url})


def test_budget_with_llm_must_stay_below_claim_idle():
    env = {"EMBED_BASE_URL": URL, "EMBED_TIMEOUT_S": "5"}
    EmbedSettings.from_env(env, claim_min_idle_ms=60000, llm_doc_budget_s=54)
    with pytest.raises(ConfigError, match="EMBED_TIMEOUT_S"):
        EmbedSettings.from_env(env, claim_min_idle_ms=60000, llm_doc_budget_s=55)


def test_budget_without_llm():
    with pytest.raises(ConfigError, match="EMBED_TIMEOUT_S"):
        EmbedSettings.from_env({"EMBED_BASE_URL": URL, "EMBED_TIMEOUT_S": "60"}, claim_min_idle_ms=60000)


# ---- gate -------------------------------------------------------------------------------------


def test_gate_defaults():
    g = GateSettings.from_env({})
    assert g.enabled is True and g.sim_threshold == 0.45


@pytest.mark.parametrize("raw,expected", [("false", False), ("0", False), ("no", False), ("FALSE", False),
                                          ("true", True), ("1", True), ("yes", True), ("", True)])
def test_gate_enabled_parsing(raw, expected):
    assert GateSettings.from_env({"GATE_ENABLED": raw}).enabled is expected


def test_gate_enabled_invalid():
    with pytest.raises(ConfigError, match="GATE_ENABLED"):
        GateSettings.from_env({"GATE_ENABLED": "maybe"})


@pytest.mark.parametrize("raw", ["0", "1.01", "-0.1", "abc", "nan"])
def test_gate_threshold_range(raw):
    with pytest.raises(ConfigError, match="GATE_SIM_THRESHOLD"):
        GateSettings.from_env({"GATE_SIM_THRESHOLD": raw})


def test_gate_threshold_upper_bound_inclusive():
    assert GateSettings.from_env({"GATE_SIM_THRESHOLD": "1"}).sim_threshold == 1.0


# ---- near-dup ---------------------------------------------------------------------------------


def test_neardup_defaults():
    n = NearDupSettings.from_env({})
    assert (n.num_perm, n.bands, n.threshold, n.max_chars, n.ttl_s) == (128, 32, 0.8, 50000, 2592000)
    assert n.rows == 4


def test_neardup_perm_divisible_by_bands():
    with pytest.raises(ConfigError, match="NEARDUP_BANDS"):
        NearDupSettings.from_env({"NEARDUP_NUM_PERM": "128", "NEARDUP_BANDS": "30"})


def test_neardup_bands_not_above_perm():
    with pytest.raises(ConfigError, match="NEARDUP_BANDS"):
        NearDupSettings.from_env({"NEARDUP_NUM_PERM": "16", "NEARDUP_BANDS": "32"})


@pytest.mark.parametrize("key,value", [("NEARDUP_NUM_PERM", "0"), ("NEARDUP_THRESHOLD", "0"),
                                       ("NEARDUP_THRESHOLD", "1.5"), ("NEARDUP_MAX_CHARS", "x"),
                                       ("NEARDUP_TTL_S", "-5")])
def test_neardup_bad_values(key, value):
    with pytest.raises(ConfigError, match=key):
        NearDupSettings.from_env({key: value})
