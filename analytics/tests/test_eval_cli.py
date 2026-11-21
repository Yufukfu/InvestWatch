"""gold-set-evaluation: "Command line and compose service" (exit codes, streams) and the CLI side of the others."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import make_doc
from investwatch_analytics.evaluation import __main__ as cli
from investwatch_analytics.evaluation import store
from investwatch_analytics.storage import StoreUnavailable

ANALYTICS = Path(__file__).resolve().parents[1]


def gold(tmp_path: Path, *modules: str, raw: str | None = None) -> Path:
    path = tmp_path / "gold.jsonl"
    if raw is None:
        lines = []
        for n, m in enumerate(modules or ("M2",), start=1):
            doc = make_doc(id=f"00000000-0000-4000-8000-{n:012d}",
                           text="Reklama. Zentrovia Dom Maklerski S.A. Zarobisz 12% rocznie.",
                           source_kind="firm_own" if m == "M2" else "third_party")
            lines.append(json.dumps({"id": f"g{n}", "origin": "synthetic", "basis": "test", "document": doc,
                                     "expect": {m: {"label": "positive", "rules": {}}}}, ensure_ascii=False))
        raw = "\n".join(lines) + "\n"
    path.write_text(raw, encoding="utf-8")
    return path


@pytest.fixture
def no_db(monkeypatch):
    calls = []
    monkeypatch.setattr(store, "write_run", lambda *a, **k: calls.append(a) or pytest.fail("database used"))
    return calls


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("DATABASE_URL", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_report_only_run(tmp_path, capsys, no_db):
    assert cli.main(["--gold", str(gold(tmp_path))]) == 0
    out = capsys.readouterr()
    report = json.loads(out.out)
    assert report["modules"]["M2"]["status"] == "evaluated"
    assert report["store"] is None
    assert no_db == []
    for line in out.err.strip().splitlines():
        json.loads(line)  # logs are JSON lines on stderr


def test_empty_gold_set(tmp_path, capsys, no_db):
    assert cli.main(["--gold", str(gold(tmp_path, raw=""))]) == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert "no labeled document" in out.err


def test_unknown_rule_id_exits_2_before_analysis(tmp_path, capsys, no_db, monkeypatch):
    raw = gold(tmp_path).read_text(encoding="utf-8").replace('"rules": {}', '"rules": {"R19": "fail"}')
    monkeypatch.setattr(cli, "evaluate", lambda *a, **k: pytest.fail("analyzed"))
    assert cli.main(["--gold", str(gold(tmp_path, raw=raw))]) == 2
    assert "R19" in capsys.readouterr().err


def test_db_without_database_url(tmp_path, capsys, no_db):
    assert cli.main(["--gold", str(gold(tmp_path)), "--db"]) == 2
    assert "DATABASE_URL" in capsys.readouterr().err


def test_db_with_malformed_url_exits_before_analysis(tmp_path, capsys, no_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:s3cret-pw@[bad")
    monkeypatch.setattr(cli, "evaluate", lambda *a, **k: pytest.fail("analyzed"))
    assert cli.main(["--gold", str(gold(tmp_path)), "--db"]) == 2
    err = capsys.readouterr().err
    assert "malformed" in err and "s3cret-pw" not in err


def test_llm_without_base_url(tmp_path, capsys, no_db):
    assert cli.main(["--gold", str(gold(tmp_path)), "--llm"]) == 2
    assert "LLM_BASE_URL" in capsys.readouterr().err


def test_llm_in_a_build_without_a_judge(tmp_path, capsys, no_db, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setattr(cli, "_judge_factory", lambda: None)
    assert cli.main(["--gold", str(gold(tmp_path)), "--llm"]) == 2
    assert "no LLM judge in this build" in capsys.readouterr().err


def test_not_run_module_exits_1_and_stores_the_others(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    stored = []
    monkeypatch.setattr(store, "write_run", lambda dsn, report, **k: stored.append(report) or {"M2": "inserted"})
    path = gold(tmp_path, "M2", "M1")
    if cli.load_build().catalogues.get("M1") is not None:
        pytest.skip("M1 is in this build")
    assert cli.main(["--gold", str(path), "--db"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["modules"]["M1"]["status"] == "not_run"
    assert report["store"] == {"M2": "inserted"}
    assert stored and stored[0]["modules"]["M2"]["status"] == "evaluated"


def test_store_unavailable_exits_3_with_report(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")

    def down(*a, **k):
        raise StoreUnavailable("OperationalError: connection refused")

    monkeypatch.setattr(store, "write_run", down)
    assert cli.main(["--gold", str(gold(tmp_path)), "--db"]) == 3
    out = capsys.readouterr()
    assert json.loads(out.out)["modules"]["M2"]["status"] == "evaluated"
    assert "calibration run not stored" in out.err


def test_module_option_restricts_evaluation(tmp_path, capsys, no_db):
    assert cli.main(["--gold", str(gold(tmp_path, "M2", "M3")), "--module", "M2"]) == 0
    assert set(json.loads(capsys.readouterr().out)["modules"]) == {"M2"}


def test_module_option_still_validates_other_labels(tmp_path, capsys, no_db):
    raw = gold(tmp_path, "M3").read_text(encoding="utf-8").replace('"rules": {}', '"rules": {"S3.99": "fail"}')
    assert cli.main(["--gold", str(gold(tmp_path, raw=raw)), "--module", "M2"]) == 2


def test_gold_hash_is_the_file_hash(tmp_path, capsys, no_db):
    import hashlib

    path = gold(tmp_path)
    cli.main(["--gold", str(path)])
    assert json.loads(capsys.readouterr().out)["run"]["gold_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_bad_registry_exits_2(tmp_path, capsys, no_db):
    bad = tmp_path / "registry.csv"
    bad.write_text("id,name\n", encoding="utf-8")
    assert cli.main(["--gold", str(gold(tmp_path)), "--registry", str(bad)]) == 2


@pytest.mark.parametrize("argv", [["eval/run.py", "--help"], ["-m", "investwatch_analytics.evaluation", "--help"]])
def test_both_entry_points(argv):
    r = subprocess.run([sys.executable, *argv], cwd=ANALYTICS, capture_output=True, text=True,
                       env={"PYTHONPATH": str(ANALYTICS / "src"), "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")})
    assert r.returncode == 0, r.stderr
    assert "--gold" in r.stdout and "--db" in r.stdout
