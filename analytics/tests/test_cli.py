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
    assert {f["module"] for f in findings} == {"M1", "M2", "M3"}
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
    path.write_text(json.dumps([make_doc(text="Reklama. Konto w Alfa Inwestycje.")]), encoding="utf-8-sig")
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


def test_cli_analysis_error_skips_document_and_exits_1(tmp_path, capsys, monkeypatch):
    first = make_doc(id="33333333-3333-4333-8333-333333333333", text="Tajny tekst klienta. Zarabiaj 18%!")
    second = make_doc(text="Konto Alfa Inwestycje. Zarabiaj 18%!")
    real = cli.analyze

    def flaky(doc, **kw):
        if doc.id == first["id"]:
            raise RuntimeError("boom " + doc.text)
        return real(doc, **kw)

    monkeypatch.setattr(cli, "analyze", flaky)
    path = tmp_path / "batch.json"
    path.write_text(json.dumps([first, second]), encoding="utf-8")
    assert cli.main([str(path)]) == 1
    out, err = capsys.readouterr()
    [finding] = json.loads(out)
    assert finding["document_id"] == second["id"]
    [line] = [json.loads(ln) for ln in err.splitlines() if "analysis failed" in ln]
    assert line["document_id"] == first["id"] and line["error_type"] == "RuntimeError" and line["level"] == "error"
    assert "Tajny tekst" not in err


def test_cli_catalogue_with_list_root_exits_2(tmp_path, capsys, monkeypatch):
    from investwatch_analytics.rules import engine

    bad = tmp_path / "rules.yaml"
    bad.write_text("- id: R1\n", encoding="utf-8")
    monkeypatch.setattr(engine, "DEFAULT_CATALOGUE", bad)
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(make_doc()), encoding="utf-8")
    assert cli.main([str(path)]) == 2
    assert capsys.readouterr().out == ""


def test_cli_bad_signal_catalogue_exits_2(tmp_path, capsys, monkeypatch):
    from investwatch_analytics import pipeline
    from investwatch_analytics.rules import engine

    bad = tmp_path / "m1.yaml"
    bad.write_text("rules:\n  - {id: S1.1, name: x, severity: low, weight: 1}\n", encoding="utf-8")  # no bias
    monkeypatch.setitem(engine.MODULE_CATALOGUES, "M1", bad)
    pipeline.default_signal_catalogues.cache_clear()
    try:
        path = tmp_path / "doc.json"
        path.write_text(json.dumps(make_doc(text="Konto w Alfa Inwestycje.")), encoding="utf-8")
        assert cli.main([str(path)]) == 2
        assert capsys.readouterr().out == ""
    finally:
        pipeline.default_signal_catalogues.cache_clear()


def test_cli_writes_utf8_whatever_the_console_code_page(tmp_path):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(make_doc(source_kind="third_party", platform="instagram",
                                        url="https://www.instagram.com/p/E1/", author={"handle": "@ola"},
                                        text="Konto w Alfa Inwestycje DM 🚀")), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    env["PYTHONIOENCODING"] = "cp1250"  # a Windows console code page that cannot encode the emoji
    run = subprocess.run([sys.executable, "-m", "investwatch_analytics.cli", str(path)], capture_output=True, env=env,
                         cwd=ROOT)
    assert run.returncode == 0, run.stderr.decode("utf-8", "replace")
    assert "🚀" in json.loads(run.stdout.decode("utf-8"))[0]["content_excerpt"]
