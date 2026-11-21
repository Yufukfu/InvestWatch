"""Registry matching at the size of the real KNF register (spec document-analysis "Firm registry matching",
change analytics-knf-registry design decision 9). No network: firms are hand-made or built from snapshots."""

from __future__ import annotations

import random
import time

import pytest
from knf_fixtures import FakeFetcher

from investwatch_analytics.knf.build import build
from investwatch_analytics.knf.fetch import fetch_all
from investwatch_analytics.registry import Firm, Registry, core_name

URL = "https://x.example.org/artykul"


def _reg(*firms: tuple[str, str] | tuple[str, str, tuple[str, ...]]) -> Registry:
    out = []
    for i, f in enumerate(firms):
        name, type_ = f[0], f[1]
        aliases = f[2] if len(f) > 2 else ()
        out.append(Firm(id=f"{i:08x}-0000-4000-8000-000000000000", name=name, type=type_, country=None,
                        aliases=aliases, domains=(), source_url=None))
    return Registry(out)


@pytest.mark.parametrize("name,core", [
    ("Admiral Markets AS", "Admiral Markets"),
    ("IG Europe GmbH", "IG Europe"),
    ("LYNX B.V.", "LYNX"),
    ("42 financial services a.s.", "42 financial services"),
    ("WOOD & Company Financial Services a.s.", "WOOD & Company Financial Services"),
    ("Some Firm s.r.o.", "Some Firm"),
    ("ABF TRADE EU LIMITED", "ABF TRADE EU"),
    ("Mariana UFP SAS", "Mariana UFP"),
    ("360 Treasury Systems AG", "360 Treasury Systems"),
    ("Nordnet Bank AB", "Nordnet Bank"),
    ("Alaric Securities OOD", "Alaric Securities"),
    ("TCW Italy SIM S.p.A.", "TCW Italy SIM"),
    ("Bitstamp finančne storitve d.o.o.", "Bitstamp finančne storitve"),
    ("Saxo Bank A/S", "Saxo Bank"),
    ("Erste Group Bank AG Spółka Akcyjna Oddział w Polsce", "Erste Group Bank"),
    ("Wise Assets Europe AS", "Wise Assets Europe"),  # "Assets" is a word, not the form AS
    ("AS Trade Ltd", "AS Trade"),  # a short form is stripped only at the end
    ("Nordic AS Partners Ltd", "Nordic AS Partners"),
    ("Kancelaria X sp. k.", "Kancelaria X"),
    ("Departament Maklerski Banku Handlowego", "Banku Handlowego"),
])
def test_core_name_strips_knf_legal_forms(name, core):
    assert core_name(name) == core


def test_foreign_legal_form_stripped_in_matching():
    m = _reg(("Admiral Markets AS", "foreign_no_branch")).match("Konto w Admiral Markets od dziś.", URL)
    assert m is not None and m.method == "name" and m.evidence == "Admiral Markets" and m.confidence >= 0.9


def test_short_word_in_lower_case_never_matches():
    reg = _reg(("EXT Ltd", "foreign_branch"), ("Nova AG", "foreign_no_branch"))
    assert reg.match("The next step is bossa nova and ext.", URL) is None


def test_seven_letter_word_is_still_short_eight_is_not():
    reg = _reg(("Quantix AG", "foreign_no_branch", ("Quantix",)), ("Ausprime Ltd", "foreign_no_branch", ("Ausprime",)))
    assert reg.match("quantix", URL) is None
    m = reg.match("konto w ausprime", URL)
    assert m is not None and m.evidence == "ausprime"


def test_short_core_matched_by_its_full_name():
    m = _reg(("Nova AG", "foreign_no_branch")).match("Oferta Nova AG dla klientów.", URL)
    assert m is not None and m.method == "name" and m.evidence == "Nova AG"


def test_short_brand_matched_as_a_capitalized_word():
    reg = _reg(("XTB S.A.", "brokerage_house", ("XTB",)))
    m = reg.match("Otwórz konto w XTB i handluj.", URL)
    assert m is not None and m.method == "name" and m.evidence == "XTB"
    assert reg.match("otwórz konto w xtb", URL) is None


def test_short_brand_written_lower_first_matches_as_written():
    reg = _reg(("mBANK S.A. – Biuro Maklerskie mBank", "brokerage_bank"))
    m = reg.match("Rachunek maklerski w mBank to wygoda.", URL)
    assert m is not None and m.evidence == "mBank"


def test_find_name_applies_the_case_guard():
    reg = _reg(("Nova AG", "foreign_no_branch", ("Nova",)))
    firm = reg.firms[0]
    assert reg.find_name(firm, "bossa nova") is None
    assert reg.find_name(firm, "Nova ma nową ofertę") == "Nova"


def test_shared_core_goes_to_the_polish_firm():
    reg = _reg(("XTB Ltd", "foreign_no_branch"), ("XTB S.A.", "brokerage_house"))
    m = reg.match("Platforma XTB w reklamie.", URL)
    assert m is not None and m.firm.name == "XTB S.A."


def test_shared_core_of_equal_types_matches_neither():
    reg = _reg(("Alpha Capital Ltd", "foreign_no_branch"), ("Alpha Capital GmbH", "foreign_no_branch"))
    assert reg.match("Alpha Capital zaprasza.", URL) is None
    assert reg.match("Alpha Capitl zaprasza.", URL) is None  # nor fuzzily
    m = reg.match("Alpha Capital GmbH zaprasza.", URL)
    assert m is not None and m.firm.name == "Alpha Capital GmbH"  # the full name still identifies one


def test_multi_word_core_still_fuzzy_matches():
    m = _reg(("Wise Assets Europe AS", "foreign_no_branch")).match("Konto w Wise Asets Europe.", URL)
    assert m is not None and m.method == "fuzzy"


def test_short_core_never_fuzzy_matches():
    assert _reg(("Trigon S.A.", "brokerage_house")).match("Trigan oferuje.", URL) is None


def test_firm_without_domains_is_never_matched_by_domain():
    reg = _reg(("Alfa Inwestycje S.A.", "brokerage_house"))
    assert reg.match("Zwykły tekst.", "https://alfa-inwestycje.pl/") is None
    assert reg.match("Zwykły tekst.", "https://") is None


def test_bank_line_and_its_core_match():
    reg = _reg(("mBANK S.A. – Biuro Maklerskie mBank", "brokerage_bank"))
    assert reg.match("Biuro Maklerskie mBank informuje.", URL).evidence == "Biuro Maklerskie mBank"


@pytest.fixture(scope="module")
def big_registry() -> Registry:
    firms, _ = build(fetch_all(FakeFetcher()))
    out = []
    for i in range(1000):
        f = firms[i % len(firms)]
        out.append(Firm(id=f"{i:08x}-0000-4000-8000-000000000000", name=f"{f.name} {i}", type=f.type,
                        country=f.country, aliases=tuple(f"{a} {i}" for a in f.aliases), domains=(),
                        source_url=None))
    return Registry(out)


def test_real_size_registry_within_budget(big_registry):
    rng = random.Random(7)
    words = ("inwestycja zysk konto rachunek akcje broker forex kryptowaluty oferta Polska rynek kapitał "
             "ryzyko Markets Capital Europe Bank Securities Trade").split()
    text = " ".join(rng.choice(words) for _ in range(3000))[:20000]
    target = big_registry.firms[123]
    timings = []
    for _ in range(3):  # best of three, so a busy CI runner does not fail the budget
        started = time.perf_counter()
        m = big_registry.match(text + " " + target.name, URL)
        timings.append(time.perf_counter() - started)
    assert min(timings) < 1.0
    assert m is not None and m.firm is target and m.method == "name"


# ---- review fixes (group 3) -------------------------------------------------------------------------


def test_find_name_on_a_domain_matched_firm_quotes_a_form_another_firm_owns():
    reg = Registry([
        Firm(id="00000000-0000-4000-8000-000000000001", name="X-Trade Brokers Dom Maklerski S.A.",
             type="brokerage_house", country="PL", aliases=("XTB",), domains=(), source_url=None),
        Firm(id="00000000-0000-4000-8000-000000000002", name="XTB Limited", type="foreign_no_branch",
             country="CY", aliases=("XTB",), domains=("xtb.cy",), source_url=None),
    ])
    m = reg.match("Otwórz konto w XTB już dziś", "https://xtb.cy/pl")
    assert m.firm.name == "XTB Limited" and m.method == "domain"
    assert reg.find_name(m.firm, "Otwórz konto w XTB już dziś") == "XTB"


def test_short_acronym_only_in_capitals():
    reg = _reg(("EVO Ltd", "foreign_no_branch", ("EVO",)))
    assert reg.match("Nowa wersja Evo jest szybsza.", URL) is None
    assert reg.match("Konto w EVO.", URL).evidence == "EVO"


def test_short_word_longer_than_an_acronym_matches_title_case():
    reg = _reg(("TRIGON DOM MAKLERSKI S.A.", "brokerage_house", ("TRIGON",)))
    assert reg.match("Raport Trigon o rynku.", URL).evidence == "Trigon"


def test_turkish_dotted_capital_i_is_not_lost_by_the_prefilter():
    m = _reg(("ING Bank Śląski S.A.", "brokerage_bank")).match("İNG Bank Śląski poleca", URL)
    assert m is not None and m.method == "name"


@pytest.mark.parametrize("name,core", [
    ("Revolut Securities Europe UAB", "Revolut Securities Europe"),
    ("Concorde Securities Zrt.", "Concorde Securities"),
    ("Erste Befektetési Kft.", "Erste Befektetési"),
    ("Firma Inwestycyjna S.A. w restrukturyzacji", "Firma Inwestycyjna"),
    ("Stary Dom Maklerski S.A. w likwidacji", "Stary"),
])
def test_more_knf_legal_forms(name, core):
    assert core_name(name) == core


def test_brand_casing_with_an_inner_capital_matches():
    # KNF writes "Etoro (Europe) Ltd"; ads write "eToro". A plain lower-case word still never matches.
    reg = _reg(("Etoro (Europe) Ltd", "foreign_no_branch", ("Etoro",)))
    assert reg.match("Platforma eToro dla początkujących", URL).evidence == "eToro"
    assert reg.match("platforma etoro", URL) is None
