"""Wiring the judge into the worker, the CLI and compose (analytics-llm-p0 task group 12). Stub server only."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import fakeredis
import pytest
import yaml

from conftest import NOW, make_doc
from llm_stub import Reply
from investwatch_analytics.config import LlmSettings, Settings
from investwatch_analytics.llm.judge import JudgeOutcome, LlmVerdict
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue

ALFA = (
    "Konto Premium Alfa Inwestycje. Zarabiaj nawet do 18% rocznie na portfelu ETF! "
    "Dołącz do 50 000 zadowolonych inwestorów. Działamy pod nadzorem KNF – Twoje środki są bezpieczne. "
    "Otwórz konto w 5 minut. *Inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału."
)
KNF = "Działamy pod nadzorem KNF – Twoje środki są bezpieczne."
ANALYTICS = Path(__file__).resolve().parents[1]
SEED = ANALYTICS / "registry" / "seed.csv"
WORKER_ENV = {"DATABASE_URL": "postgresql://u:pw%zz@h/db", "REDIS_URL": "redis://127.0.0.1:1/0"}


def log_text(caplog) -> str:
    return "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)


# ---- build_judge -------------------------------------------------------------------------------------


def test_build_judge_disabled_is_none():
    from investwatch_analytics.llm import build_judge

    assert build_judge(LlmSettings.from_env({})) is None


def test_build_judge_enabled():
    from investwatch_analytics.llm import build_judge
    from investwatch_analytics.llm.judge import HttpJudge

    j = build_judge(LlmSettings.from_env({"LLM_BASE_URL": "http://ollama:11434/v1", "LLM_MODEL": "gemma3:4b"}))
    assert isinstance(j, HttpJudge) and j.model_name == "gemma3:4b"


# ---- worker -------------------------------------------------------------------------------------------


def test_worker_exits_2_when_the_model_is_missing(capsys):
    from investwatch_analytics.worker import main

    env = {**WORKER_ENV, "LLM_BASE_URL": "http://ollama:11434/v1",
           "LLM_MODEL": ""}
    assert main(env) == 2
    assert "LLM_MODEL" in capsys.readouterr().out


def test_worker_exits_2_when_the_budget_exceeds_claim_idle(capsys):
    from investwatch_analytics.worker import main

    env = {**WORKER_ENV, "LLM_BASE_URL": "http://ollama:11434/v1",
           "LLM_MODEL": "gemma3:4b", "LLM_DOC_BUDGET_S": "90", "CLAIM_MIN_IDLE_MS": "60000"}
    assert main(env) == 2
    assert "LLM_DOC_BUDGET_S" in capsys.readouterr().out


@pytest.mark.parametrize("env, mode", [
    ({}, "disabled"),
    ({"LLM_BASE_URL": "http://ollama:11434/v1", "LLM_MODEL": "gemma3:4b"}, "local"),
    ({"LLM_BASE_URL": "https://api.example.com/v1", "LLM_MODEL": "m", "LLM_API_KEY": "sk-test-123"}, "hosted"),
])
def test_worker_logs_the_llm_mode_and_never_the_key(capsys, env, mode):
    from investwatch_analytics.worker import main

    assert main({**WORKER_ENV, **env}) == 2  # stops later, at the malformed DATABASE_URL
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert any(rec.get("llm_mode") == mode for rec in lines)
    assert all("sk-test-123" not in json.dumps(rec) for rec in lines)


class FakeJudge:
    model_name = "gemma3:4b"

    def __init__(self):
        self.calls = 0

    def judge(self, **kw):
        self.calls += 1
        return JudgeOutcome(verdicts={"R17": LlmVerdict("R17", "fail", KNF, "Sugeruje aprobatę.")}, model="gemma3:4b")


def test_worker_passes_the_judge_to_analyze():
    from investwatch_analytics.testing import InMemoryStore, NoopPublisher
    from investwatch_analytics.worker import GROUP, Worker, WorkerConfig

    store = InMemoryStore()
    doc_id = "22222222-2222-4222-8222-222222222222"
    store.put_document_row(make_doc(id=doc_id, text=ALFA))
    r = fakeredis.FakeRedis(decode_responses=True)
    judge = FakeJudge()
    w = Worker(r, store, NoopPublisher(), registry=Registry.from_csv(Path(__file__).resolve().parents[1] / "registry" / "seed.csv"),
               catalogue=Catalogue.load(), config=WorkerConfig(consumer="w1", block_ms=10),
               now=lambda: NOW, sleep=lambda s: None, jitter=lambda: 0.0, judge=judge)
    w.ensure_group()
    r.xadd(w._config.stream, {"document_id": doc_id, "schema": "v1"})
    w.run_once()
    assert judge.calls == 1
    [finding] = store.findings_for_document(doc_id)
    assert finding.model.llm == "gemma3:4b"
    assert r.xpending(w._config.stream, GROUP)["pending"] == 0


# ---- CLI ----------------------------------------------------------------------------------------------


def write_doc(tmp_path) -> Path:
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(make_doc(text=ALFA, url="https://alfa-inwestycje.example.com/x"), ensure_ascii=False),
                    encoding="utf-8")
    return path


def test_cli_uses_the_judge_when_configured(stub_llm, tmp_path, capsys, monkeypatch):
    from investwatch_analytics import cli

    monkeypatch.setenv("LLM_BASE_URL", stub_llm.base_url)
    monkeypatch.setenv("LLM_MODEL", "gemma3:4b")
    monkeypatch.setenv("REGISTRY_CSV", str(SEED))  # the fictional Alfa firm, not the real KNF snapshot
    stub_llm.script.append(Reply.results({"rule_id": "R17", "result": "fail", "evidence_quote": KNF,
                                          "explanation": "Sugeruje aprobatę."}))
    assert cli.main([str(write_doc(tmp_path))]) == 0
    [f] = json.loads(capsys.readouterr().out)
    assert f["model"]["llm"] == "gemma3:4b" and len(stub_llm.requests) == 1


def test_cli_no_llm_forces_rules_only(stub_llm, tmp_path, capsys, monkeypatch):
    from investwatch_analytics import cli

    monkeypatch.setenv("LLM_BASE_URL", stub_llm.base_url)
    monkeypatch.setenv("LLM_MODEL", "gemma3:4b")
    monkeypatch.setenv("REGISTRY_CSV", str(SEED))
    assert cli.main(["--no-llm", str(write_doc(tmp_path))]) == 0
    [f] = json.loads(capsys.readouterr().out)
    assert f["model"]["llm"] is None and stub_llm.requests == []


def test_cli_bad_llm_config_exits_2(tmp_path, capsys, monkeypatch):
    from investwatch_analytics import cli

    monkeypatch.setenv("LLM_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "")
    assert cli.main([str(write_doc(tmp_path))]) == 2
    assert capsys.readouterr().out == ""


def test_cli_mocks_stay_contract_valid_with_a_judge(stub_llm, contracts_dir, tmp_path, capsys, monkeypatch,
                                                    finding_validator):
    from investwatch_analytics import cli

    monkeypatch.setenv("LLM_BASE_URL", stub_llm.base_url)
    monkeypatch.setenv("LLM_MODEL", "gemma3:4b")
    stub_llm.default = Reply.results({"rule_id": "R17", "result": "fail", "evidence_quote": KNF, "explanation": "x"})
    assert cli.main([str(contracts_dir / "mocks" / "documents.json")]) == 0
    for f in json.loads(capsys.readouterr().out):
        assert [e.message for e in finding_validator.iter_errors(f)] == []


# ---- compose ------------------------------------------------------------------------------------------


def test_compose_passes_llm_env_and_joins_egress():
    svc = yaml.safe_load((ANALYTICS / "compose.yaml").read_text(encoding="utf-8"))["services"]["analytics"]
    env = svc["environment"]
    for key in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_TIMEOUT_S", "LLM_DOC_BUDGET_S", "LLM_CHUNK_CHARS",
                "LLM_MAX_CHUNKS"):
        assert key in env, key
    assert set(svc["networks"]) == {"data", "egress"}


def test_env_example_documents_every_llm_variable():
    text = (ANALYTICS / ".env.example").read_text(encoding="utf-8")
    for key in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_TIMEOUT_S", "LLM_DOC_BUDGET_S", "LLM_CHUNK_CHARS",
                "LLM_MAX_CHUNKS", "LLM_CACHE_TTL_S", "LLM_BREAKER_FAILURES", "LLM_BREAKER_COOLDOWN_S"):
        assert f"{key}=" in text, key
    assert "http://ollama:11434/v1" in text and "gemma3:4b" in text


def test_worker_main_builds_the_judge_from_env(monkeypatch):
    from investwatch_analytics import worker
    from investwatch_analytics.llm.judge import HttpJudge

    class Built(Exception):
        pass

    seen = {}

    class FakeWorker:
        def __init__(self, *args, **kwargs):
            seen.update(kwargs)
            raise Built  # stop main() before it touches the network

    monkeypatch.setattr(worker, "Worker", FakeWorker)
    env = {"DATABASE_URL": "postgresql://u@127.0.0.1:1/db", "REDIS_URL": "redis://127.0.0.1:1/0",
           "LLM_BASE_URL": "http://ollama:11434/v1", "LLM_MODEL": "gemma3:4b"}
    with pytest.raises(Built):
        worker.main(env)
    assert isinstance(seen["judge"], HttpJudge) and seen["judge"].model_name == "gemma3:4b"
