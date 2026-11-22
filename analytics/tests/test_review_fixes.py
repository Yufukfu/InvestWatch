"""analytics-worker-review-fixes (PR #26 review): registry warning, clean title, test helpers out, settings."""

from __future__ import annotations

import shutil
import subprocess
import sys

from conftest import NOW, make_doc
from investwatch_analytics.config import SEED_REGISTRY, Settings, uses_seed_registry
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.pipeline import analyze
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue
from investwatch_analytics.worker import main

# DATABASE_URL that fails only at store creation, so main() returns 2 right after loading the registry.
STOPS_AFTER_REGISTRY = {"DATABASE_URL": "postgresql://u:pw%zz@h/db", "REDIS_URL": "redis://127.0.0.1:1/0"}


def test_settings_read_an_explicit_mapping(tmp_path):
    csv = tmp_path / "knf.csv"
    s = Settings.from_env({"REGISTRY_CSV": str(csv), "LOG_LEVEL": "debug"})
    assert (s.registry_csv, s.log_level) == (csv, "DEBUG")


SEED_ENV = {"REGISTRY_CSV": str(SEED_REGISTRY)}


def test_uses_seed_registry():
    assert uses_seed_registry(Settings.from_env(SEED_ENV)) is True
    assert uses_seed_registry(Settings.from_env({})) is False  # the default is the real KNF snapshot
    assert uses_seed_registry(Settings.from_env({"REGISTRY_CSV": "/data/knf.csv"})) is False


def test_worker_warns_when_the_bundled_seed_is_loaded(capsys):
    assert main({**STOPS_AFTER_REGISTRY, **SEED_ENV}) == 2
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if '"registry_seed"' in line]
    assert len(lines) == 1 and '"level": "warning"' in lines[0] and "REGISTRY_CSV" in lines[0]


def test_no_warning_with_a_real_registry_file(tmp_path, capsys):
    real = tmp_path / "knf.csv"
    shutil.copy(SEED_REGISTRY, real)  # same content, another path: not the bundled seed
    assert main({**STOPS_AFTER_REGISTRY, "REGISTRY_CSV": str(real)}) == 2
    assert '"registry_seed"' not in capsys.readouterr().out


def test_clean_title_names_the_checked_rules():
    registry = Registry.from_csv(SEED_REGISTRY)
    text = ("Reklama. Bank Przykładowy S.A. – Biuro Maklerskie. Otwórz IKE i inwestuj długoterminowo. "
            "Inwestowanie w instrumenty finansowe wiąże się z ryzykiem utraty części lub całości zainwestowanego kapitału. "
            # IKE is a tax reference: without the disclaimer of the m2-bank-ok mock, R16 fails (analytics-m2-p1-rules).
            "Traktowanie podatkowe zależy od indywidualnej sytuacji klienta i może ulec zmianie.")
    [f] = analyze(ScrapedDocument.model_validate(make_doc(text=text)), registry=registry, catalogue=Catalogue.load(), now=NOW)
    assert f.score == 0
    checked = [r.rule_id for r in f.rules if r.result != "not_applicable"]
    assert f.title.endswith("brak naruszeń w regułach " + ", ".join(checked))
    assert "sprawdzonych regułach" not in f.title


def test_worker_does_not_load_test_helpers():
    code = "import sys, investwatch_analytics.worker; print('investwatch_analytics.testing' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "False"


def test_helpers_live_in_testing():
    from investwatch_analytics import events, storage, testing

    assert hasattr(testing, "InMemoryStore") and hasattr(testing, "NoopPublisher")
    assert not hasattr(storage, "InMemoryStore") and not hasattr(events, "NoopPublisher")


def test_title_when_no_rule_applied():
    from investwatch_analytics.modules.m2 import _texts

    title, _ = _texts([], None)
    assert title == "Nieznana firma: żadna reguła nie miała zastosowania"
