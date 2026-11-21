"""Default registry and start-up provenance (spec knf-registry-loader "Default registry and provenance at
start-up"), and R1 on the official name (spec m2-compliance-rules "R1 firm identification")."""

from __future__ import annotations

import json
import shutil

import pytest
from conftest import make_doc

from investwatch_analytics.config import KNF_REGISTRY, SEED_REGISTRY, Settings, registry_provenance
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Firm, Registry
from investwatch_analytics.rules.engine import Catalogue, Context, run_rules
from investwatch_analytics.worker import main

STOPS_AFTER_REGISTRY = {"DATABASE_URL": "postgresql://u:pw%zz@h/db", "REDIS_URL": "redis://127.0.0.1:1/0"}


def _logs(capsys) -> list[dict]:
    return [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]


def _by_reason(logs, reason):
    return [l for l in logs if l.get("reason") == reason]


def test_default_is_the_real_registry_with_its_snapshot_date(capsys):
    assert main(dict(STOPS_AFTER_REGISTRY)) == 2  # stops right after loading the registry
    logs = _logs(capsys)
    (loaded,) = _by_reason(logs, "registry_loaded")
    meta = json.loads(KNF_REGISTRY.with_name("knf.meta.json").read_text(encoding="utf-8"))
    assert loaded["registry_csv"] == str(KNF_REGISTRY) and loaded["firms"] == meta["firms"] > 700
    assert loaded["snapshot_date"] == meta["fetched_at"] and loaded["level"] == "info"
    assert not _by_reason(logs, "registry_seed") and not _by_reason(logs, "registry_unverified")


def test_seed_chosen_explicitly_warns(capsys):
    assert main({**STOPS_AFTER_REGISTRY, "REGISTRY_CSV": str(SEED_REGISTRY)}) == 2
    logs = _logs(capsys)
    assert _by_reason(logs, "registry_seed") and not _by_reason(logs, "registry_unverified")
    assert _by_reason(logs, "registry_loaded")[0]["snapshot_date"] is None


def test_old_snapshot_is_never_a_warning(tmp_path, capsys):
    shutil.copy(KNF_REGISTRY, tmp_path / "knf.csv")
    (tmp_path / "knf.meta.json").write_text(json.dumps({"fetched_at": "2026-10-07T10:00:00Z", "firms": 749}),
                                            encoding="utf-8")
    assert main({**STOPS_AFTER_REGISTRY, "REGISTRY_CSV": str(tmp_path / "knf.csv")}) == 2
    logs = _logs(capsys)
    assert _by_reason(logs, "registry_loaded")[0]["snapshot_date"] == "2026-10-07T10:00:00Z"
    assert not [l for l in logs if l["level"] == "warning"]


@pytest.mark.parametrize("meta", [None, "not json", "[1, 2]"])
def test_hand_made_registry_without_provenance_is_unverified(tmp_path, capsys, meta):
    shutil.copy(SEED_REGISTRY, tmp_path / "mine.csv")
    if meta is not None:
        (tmp_path / "mine.meta.json").write_text(meta, encoding="utf-8")
    assert main({**STOPS_AFTER_REGISTRY, "REGISTRY_CSV": str(tmp_path / "mine.csv")}) == 2
    logs = _logs(capsys)
    assert _by_reason(logs, "registry_unverified")[0]["level"] == "warning"
    assert not _by_reason(logs, "registry_seed")


def test_provenance_reads_the_meta_file_next_to_the_csv(tmp_path):
    (tmp_path / "x.meta.json").write_text('{"fetched_at": "2026-11-21T20:49:58Z"}', encoding="utf-8")
    assert registry_provenance(tmp_path / "x.csv") == {"fetched_at": "2026-11-21T20:49:58Z"}
    assert registry_provenance(tmp_path / "y.csv") is None


def test_settings_default_paths():
    assert Settings.from_env({}).registry_csv == KNF_REGISTRY
    assert SEED_REGISTRY.name == "seed.csv" and SEED_REGISTRY.exists()


# ---- R1 on the official name -----------------------------------------------------------------------


def _r1(firm: Firm, text: str, url: str = "https://x.example.org/a"):
    registry = Registry([firm])
    doc = ScrapedDocument.model_validate(make_doc(text=text, url=url))
    ctx = Context(doc=doc, pre=preprocess(text), firm_match=registry.match(text, url), registry=registry)
    return next(r for r in run_rules(Catalogue.load(), ctx) if r.rule_id == "R1")


CERES = Firm(id="00000000-0000-4000-8000-000000000001", name="CERES DOM INWESTYCYJNY S.A.", type="brokerage_house",
             country="PL", aliases=("EFIX DOM MAKLERSKI S.A.", "EFIX DOM MAKLERSKI"), domains=("ceresdi.pl",),
             source_url=None)
MBANK = Firm(id="00000000-0000-4000-8000-000000000002", name="mBANK S.A. – Biuro Maklerskie mBank",
             type="brokerage_bank", country="PL", aliases=("mBANK",), domains=(), source_url=None)
ALFA = Firm(id="00000000-0000-4000-8000-000000000003", name="Alfa Inwestycje Dom Maklerski S.A.",
            type="brokerage_house", country="PL", aliases=("Alfa Inwestycje DM",), domains=(), source_url=None)


def test_only_a_former_name_is_uncertain_and_names_the_official_one():
    r = _r1(CERES, "Reklama: EFIX Dom Maklerski S.A. zaprasza do inwestowania.")
    assert r.result == "uncertain" and r.evidence == "EFIX Dom Maklerski S.A."
    assert r.explanation.startswith("W materiale użyto nazwy nieoficjalnej/dawnej")
    assert "CERES DOM INWESTYCYJNY S.A." in r.explanation


def test_official_name_passes_even_with_an_alias_present():
    r = _r1(ALFA, "Alfa Inwestycje DM, czyli Alfa Inwestycje Dom Maklerski S.A., zaprasza.")
    assert r.result == "pass" and r.evidence == "Alfa Inwestycje Dom Maklerski S.A."


def test_core_of_the_official_name_passes():
    assert _r1(ALFA, "Konto Premium Alfa Inwestycje. Zarabiaj!").result == "pass"


def test_bank_brokerage_unit_line_is_official():
    r = _r1(MBANK, "Biuro Maklerskie mBank informuje o nowej ofercie.")
    assert r.result == "pass" and r.evidence == "Biuro Maklerskie mBank"


def test_domain_only_still_fails():
    r = _r1(CERES, "Otwórz rachunek już dziś.", url="https://www.ceresdi.pl/oferta")
    assert r.result == "fail" and r.evidence is None


# ---- review fixes (group 6) -------------------------------------------------------------------------


def test_alias_containing_the_official_core_is_still_only_an_alias():
    # "Alfa Inwestycje DM" (alias) contains the official core "Alfa Inwestycje": that is no official mention.
    r = _r1(ALFA, "Alfa Inwestycje DM zaprasza.")
    assert r.result == "uncertain" and r.evidence == "Alfa Inwestycje DM"


def test_official_core_elsewhere_in_the_text_still_passes():
    r = _r1(ALFA, "Alfa Inwestycje DM zaprasza. Organizator: Alfa Inwestycje.")
    assert r.result == "pass" and r.evidence == "Alfa Inwestycje"


def test_real_registry_trade_name_containing_the_core_is_uncertain():
    registry = Registry.from_csv(KNF_REGISTRY)
    firm = next(f for f in registry.firms if "Kepler Cheuvreux" in f.aliases)
    assert registry.find_official_name(firm, "Kepler Cheuvreux zaprasza.") is None
    assert registry.find_name(firm, "Kepler Cheuvreux zaprasza.") == "Kepler Cheuvreux"


def test_handle_resolves_to_the_firm_that_owns_the_form():
    from investwatch_analytics.modules.advertiser import _firm_by_handle

    reg = Registry([
        Firm(id="00000000-0000-4000-8000-000000000011", name="XTB Ltd", type="foreign_no_branch", country="CY",
             aliases=(), domains=(), source_url=None),
        Firm(id="00000000-0000-4000-8000-000000000012", name="XTB S.A.", type="brokerage_house", country="PL",
             aliases=("XTB",), domains=(), source_url=None),
        Firm(id="00000000-0000-4000-8000-000000000013", name="mBANK S.A. – Biuro Maklerskie mBank",
             type="brokerage_bank", country="PL", aliases=(), domains=(), source_url=None),
    ])
    assert _firm_by_handle("@xtb", reg).name == "XTB S.A."
    assert _firm_by_handle("@mbank", reg).name.startswith("mBANK")  # a name line's core, no alias needed
