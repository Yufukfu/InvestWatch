from __future__ import annotations

from pathlib import Path

import pytest

from investwatch_analytics.config import Settings
from investwatch_analytics.registry import Registry, RegistryError, core_name

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
ALFA_ID = "facc6bd1-c728-5348-90a4-011b0972fea9"
BANK_ID = "1deb09a7-047b-507c-89e6-512e8ee99140"
EURO_ID = "2d7456b6-f7b5-52f2-a039-64e250001e24"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


def test_seed_loads_three_fictional_firms(registry):
    assert {f.id for f in registry.firms} == {ALFA_ID, BANK_ID, EURO_ID}


def test_default_registry_path_is_seed(monkeypatch):
    monkeypatch.delenv("REGISTRY_CSV", raising=False)
    assert Settings.from_env().registry_csv == SEED


@pytest.mark.parametrize(
    "name,core",
    [
        ("Alfa Inwestycje Dom Maklerski S.A.", "Alfa Inwestycje"),
        ("Bank Przykładowy S.A. – Biuro Maklerskie", "Bank Przykładowy"),
        ("EuroTrade Markets Ltd (oddział w Polsce)", "EuroTrade Markets"),
        ("Alfa Inwestycje DM", "Alfa Inwestycje"),
        ("Beta Sp. z o.o.", "Beta"),
    ],
)
def test_core_name_strips_legal_forms(name, core):
    assert core_name(name) == core


def test_name_without_legal_form_matches(registry):
    m = registry.match("Konto Premium Alfa Inwestycje. Zarabiaj!", "https://other.example.org/x")
    assert m is not None and m.firm.id == ALFA_ID
    assert m.method == "name" and m.confidence >= 0.9
    assert m.evidence == "Alfa Inwestycje"


def test_longest_alias_is_quoted(registry):
    text = "Reklama. Bank Przykładowy S.A. – Biuro Maklerskie. Otwórz IKE."
    m = registry.match(text, "https://x.example.org/")
    assert m.firm.id == BANK_ID
    assert m.evidence == "Bank Przykładowy S.A. – Biuro Maklerskie"
    assert m.evidence in text


def test_name_match_is_case_insensitive_and_quotes_original(registry):
    text = "Polecam ALFA  INWESTYCJE dm!"
    m = registry.match(text, "https://x.example.org/")
    assert m.firm.id == ALFA_ID and m.evidence in text and m.evidence.startswith("ALFA")


def test_name_inside_longer_word_does_not_match(registry):
    assert registry.match("Superalfa Inwestycjexyz", "https://x.example.org/") is None


def test_domain_match(registry):
    m = registry.match("Otwórz konto już dziś.", "https://www.alfa-inwestycje.example.com/konto")
    assert m.firm.id == ALFA_ID and m.method == "domain" and 0.8 <= m.confidence < 0.95
    assert m.evidence is None


def test_lookalike_domain_does_not_match(registry):
    assert registry.match("Otwórz konto.", "https://alfa-inwestycje.example.com.evil.net/") is None
    assert registry.match("Otwórz konto.", "https://fakealfa-inwestycje.example.com/") is None


def test_own_domain_beats_other_firms_name(registry):
    m = registry.match("Bank Przykładowy jest depozytariuszem.", "https://alfa-inwestycje.example.com/")
    assert m.firm.id == ALFA_ID and m.method == "domain"


def test_own_domain_with_own_name_quotes_the_name(registry):
    m = registry.match("Bank Przykładowy i Alfa Inwestycje.", "https://alfa-inwestycje.example.com/")
    assert m.firm.id == ALFA_ID and m.method == "name" and m.evidence == "Alfa Inwestycje"


def test_name_on_foreign_domain_is_not_the_page_owner(registry):
    m = registry.match("Alfa Inwestycje zaprasza.", "https://eurotrade-markets.example.com/")
    assert m.firm.id == EURO_ID and m.method == "domain"


def test_name_beats_fuzzy_regardless_of_csv_order(registry):
    m = registry.match("Klienci Alfa Inwestycji i EuroTrade.", "https://x.example.org/")
    assert m.firm.id == EURO_ID and m.method == "name"


def test_earliest_name_wins_a_tie(registry):
    m = registry.match("Bank Przykładowy i Alfa Inwestycje.", "https://x.example.org/")
    assert m.firm.id == BANK_ID
    m = registry.match("Alfa Inwestycje i Bank Przykładowy.", "https://x.example.org/")
    assert m.firm.id == ALFA_ID


def test_longest_name_wins_at_the_same_position(tmp_path):
    csv = tmp_path / "r.csv"
    csv.write_text(
        "id,name,aliases,type,country,website_domains,source_url\n"
        f"{ALFA_ID},Alfa Dom Maklerski S.A.,,brokerage_house,PL,,\n"
        f"{BANK_ID},Alfa Inwestycje Dom Maklerski S.A.,,brokerage_house,PL,,\n",
        encoding="utf-8",
    )
    m = Registry.from_csv(csv).match("Alfa Inwestycje zaprasza.", "https://x.example.org/")
    assert m.firm.id == BANK_ID and m.evidence == "Alfa Inwestycje"


def test_fuzzy_match_on_declension(registry):
    m = registry.match("Klienci Alfa Inwestycji są zadowoleni.", "https://x.example.org/")
    assert m is not None and m.firm.id == ALFA_ID and m.method == "fuzzy"
    assert 0.7 <= m.confidence < 0.9


def test_no_match(registry):
    assert registry.match("Beta Kapitał oferuje lokaty.", "https://beta.example.org/") is None


def test_find_name_in_text(registry):
    alfa = registry.get(ALFA_ID)
    assert registry.find_name(alfa, "Tylko u nas: Alfa Inwestycje DM.") == "Alfa Inwestycje DM"
    assert registry.find_name(alfa, "Brak nazwy firmy.") is None


def test_missing_file_names_it(tmp_path):
    path = tmp_path / "nope.csv"
    with pytest.raises(RegistryError, match="nope.csv"):
        Registry.from_csv(path)


def test_missing_columns_names_file(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("id,title\n1,x\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="bad.csv.*name"):
        Registry.from_csv(path)


def test_bad_row_names_file_and_line(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("id,name,type\nnot-a-uuid,Alfa,brokerage_house\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="bad.csv:2"):
        Registry.from_csv(path)


def test_unknown_type_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(f"id,name,type\n{ALFA_ID},Alfa,bank\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="bad.csv:2"):
        Registry.from_csv(path)


def test_name_of_only_legal_forms_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(f"id,name,type\n{ALFA_ID},Dom Maklerski S.A.,brokerage_house\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="bad.csv:2"):
        Registry.from_csv(path)


def test_duplicate_id_rejected(tmp_path):
    path = tmp_path / "dup.csv"
    path.write_text(f"id,name,type\n{ALFA_ID},Alfa,brokerage_house\n{ALFA_ID},Beta,brokerage_house\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="dup.csv:3"):
        Registry.from_csv(path)


def test_utf8_bom_accepted(tmp_path):
    path = tmp_path / "bom.csv"
    path.write_text(f"id,name,type\n{ALFA_ID},Alfa Inwestycje,brokerage_house\n", encoding="utf-8-sig")
    assert len(Registry.from_csv(path).firms) == 1


def test_non_utf8_file_names_it(tmp_path):
    path = tmp_path / "cp1250.csv"
    path.write_bytes(f"id,name,type\n{ALFA_ID},Bank Przykładowy,brokerage_bank\n".encode("cp1250"))
    with pytest.raises(RegistryError, match="cp1250.csv"):
        Registry.from_csv(path)


def test_fuzzy_does_not_cross_punctuation(registry):
    assert registry.match("Strategia alfa: inwestycje w obligacje.", "https://x.example.org/") is None


@pytest.mark.parametrize(
    "domain,url",
    [
        ("https://www.alfa.pl/", "https://oferta.alfa.pl/x"),
        ("www.alfa.pl", "https://alfa.pl/"),
        ("alfa.pl", "https://www.alfa.pl./konto"),
    ],
)
def test_domains_are_normalized(tmp_path, domain, url):
    path = tmp_path / "d.csv"
    path.write_text(f"id,name,type,website_domains\n{ALFA_ID},Gamma Kapitał,brokerage_house,{domain}\n", encoding="utf-8")
    m = Registry.from_csv(path).match("Otwórz konto.", url)
    assert m is not None and m.method == "domain"


def test_empty_registry_rejected(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("id,name,type\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="empty.csv"):
        Registry.from_csv(path)


def test_higher_fuzzy_confidence_beats_earlier_fuzzy(registry):
    m = registry.match("Alfa Inwestycji oraz EuroTrad Markets.", "https://x.example.org/")
    assert m.firm.id == EURO_ID and m.method == "fuzzy"
