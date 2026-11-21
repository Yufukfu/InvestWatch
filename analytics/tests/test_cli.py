from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import make_doc
from investwatch_analytics import cli

ROOT = Path(__file__).resolve().parents[1]


def test_cli_on_mocks_passes_contract_validator(contracts_dir, tmp_path):
    out = tmp_path / "findings.json"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    run = subprocess.run(
        [sys.executable, "-m", "investwatch_analytics.cli", str(contracts_dir / "mocks" / "documents.json")],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT,
    )
    assert run.returncode == 0, run.stderr
    findings = json.loads(run.stdout)
    assert isinstance(findings, list) and findings
    assert {f["module"] for f in findings} == {"M2"}
    out.write_text(run.stdout, encoding="utf-8")
    check = subprocess.run(
        [sys.executable, str(contracts_dir / "validate.py"), "finding", str(out)],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )
    assert check.returncode == 0, check.stdout + check.stderr


def test_cli_accepts_single_object(tmp_path, capsys):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(make_doc(text="Konto Alfa Inwestycje. Zarabiaj 18%!")), encoding="utf-8")
    assert cli.main([str(path)]) == 0
    [finding] = json.loads(capsys.readouterr().out)
    assert finding["document_id"] == make_doc()["id"]


def test_cli_invalid_document_exits_2(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([{"id": "x"}]), encoding="utf-8")
    assert cli.main([str(path)]) == 2
    assert capsys.readouterr().out == ""


def test_cli_reads_utf8_bom(tmp_path, capsys):
    path = tmp_path / "bom.json"
    path.write_text(json.dumps([make_doc()]), encoding="utf-8-sig")
    assert cli.main([str(path)]) == 0
    assert json.loads(capsys.readouterr().out)


def test_cli_utf16_file_exits_2(tmp_path, capsys):
    path = tmp_path / "ps.json"
    path.write_text(json.dumps([make_doc()]), encoding="utf-16")
    assert cli.main([str(path)]) == 2
    assert capsys.readouterr().out == ""


def test_cli_bad_log_level_exits_2(tmp_path, capsys, monkeypatch):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(make_doc()), encoding="utf-8")
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    assert cli.main([str(path)]) == 2
    assert capsys.readouterr().out == ""


def test_cli_missing_file_exits_2(tmp_path, capsys):
    assert cli.main([str(tmp_path / "nope.json")]) == 2
    assert capsys.readouterr().out == ""


def test_cli_bad_registry_exits_2(tmp_path, capsys, monkeypatch):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(make_doc()), encoding="utf-8")
    monkeypatch.setenv("REGISTRY_CSV", str(tmp_path / "missing.csv"))
    assert cli.main([str(path)]) == 2
    assert capsys.readouterr().out == ""


def test_cli_skips_invalid_document_and_keeps_the_rest(tmp_path, capsys):
    good = make_doc(text="Konto Alfa Inwestycje. Zarabiaj 18%!")
    bad = make_doc(id="22222222-2222-4222-8222-222222222222", text="Tajny tekst klienta 12345.")
    del bad["fetched_at"]
    path = tmp_path / "batch.json"
    path.write_text(json.dumps([good, bad]), encoding="utf-8")
    assert cli.main([str(path)]) == 0
    out, err = capsys.readouterr()
    [finding] = json.loads(out)
    assert finding["document_id"] == good["id"]
    [line] = [json.loads(ln) for ln in err.splitlines() if "invalid document" in ln]
    assert line["index"] == 1 and line["level"] == "warning"
    assert {"loc": ["fetched_at"], "type": "missing"} in line["errors"]


def test_cli_all_invalid_exits_2(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([{"id": "x"}, {"id": "y"}]), encoding="utf-8")
    assert cli.main([str(path)]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert len([ln for ln in err.splitlines() if "invalid document" in ln]) == 2


def test_cli_empty_list_is_ok(tmp_path, capsys):
    path = tmp_path / "empty.json"
    path.write_text("[]", encoding="utf-8")
    assert cli.main([str(path)]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_cli_invalid_document_log_has_no_input_values(tmp_path, capsys):
    missing = make_doc(text="Tajny tekst klienta 12345.", author={"handle": "jan.kowalski.secret"})
    del missing["fetched_at"]
    malformed = make_doc(fetched_at="not-a-date")
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([missing, malformed]), encoding="utf-8")
    assert cli.main([str(path)]) == 2
    err = capsys.readouterr().err
    assert "invalid document" in err
    for secret in ("Tajny tekst", "jan.kowalski.secret", "not-a-date"):
        assert secret not in err
