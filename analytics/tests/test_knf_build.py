"""Building registry rows (spec knf-registry-loader: "Stable firm ids", "One firm per name", "Generated aliases",
"Firm domains"). Saved snapshots and hand-made records only; no network."""

from __future__ import annotations

import uuid

import pytest
from knf_fixtures import FakeFetcher

from investwatch_analytics.knf.build import NAMESPACE, build, domains_in, firm_id, normalize_name, trade_names
from investwatch_analytics.knf.fetch import LISTS, SUMMARY_URL, FetchedList, fetch_all
from investwatch_analytics.knf.parse import parse_page

SOURCES = {s.key: s for s in LISTS}


@pytest.fixture(scope="module")
def snapshot():
    return fetch_all(FakeFetcher())


@pytest.fixture(scope="module")
def built(snapshot):
    return build(snapshot)


def _firm(firms, name):
    hits = [f for f in firms if f.name == name]
    assert len(hits) == 1, f"{name}: {len(hits)} firms"
    return hits[0]


def _record(name_html: str, **cells: str) -> str:
    """One firm table; keyword cells use `_` for spaces (`Organ_nadzoru`)."""
    rows = [("Nazwa podmiotu", name_html)] + [(k.replace("_", " "), v) for k, v in cells.items()]
    return "<table><tbody>" + "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows) + "</tbody></table>"


def _list(key: str, *tables: str) -> FetchedList:
    html = '<html><body><div id="entityTable">' + "".join(tables) + "</div></body></html>"
    return FetchedList(SOURCES[key], parse_page(html, where=key), 0, 1)


def _fetched(**lists: FetchedList) -> dict[str, FetchedList]:
    return {s.key: lists.get(s.key, FetchedList(s, [], 0, 0)) for s in LISTS}




# ---- ids --------------------------------------------------------------------------------------------


def test_id_is_uuid5_of_the_normalized_name():
    assert NAMESPACE == uuid.uuid5(uuid.NAMESPACE_URL, SUMMARY_URL)
    assert firm_id("CERES DOM INWESTYCYJNY S.A.") == str(uuid.uuid5(NAMESPACE, "ceres dom inwestycyjny s.a"))
    assert firm_id("  Ceres  Dom Inwestycyjny S.A. ") == firm_id("CERES DOM INWESTYCYJNY S.A.")
    assert normalize_name("„Bank” Przykładowy S.A.") == "bank przykładowy s.a"


def test_reload_and_reordering_give_the_same_ids(snapshot, built):
    reversed_lists = {k: FetchedList(v.source, list(reversed(v.records)), v.skipped, v.pages)
                      for k, v in reversed(list(snapshot.items()))}
    again, _ = build(reversed_lists)
    assert {f.name: f.id for f in again} == {f.name: f.id for f in built[0]}
    assert [f.name for f in again] == [f.name for f in built[0]]  # sorted by type, then name


def test_firm_moving_between_lists_keeps_its_id():
    rec = _record("IG Europe GmbH", Państwo_macierzyste="Niemcy")
    before, _ = build(_fetched(no_branch=_list("no_branch", rec)))
    after, _ = build(_fetched(branches=_list("branches", rec)))
    assert before[0].id == after[0].id and (before[0].type, after[0].type) == ("foreign_no_branch", "foreign_branch")


def test_rename_with_a_struck_former_name_keeps_the_previous_id():
    old_id = firm_id("EFIX DOM MAKLERSKI S.A.")
    rec = _record("<span>CERES DOM INWESTYCYJNY S.A.<br /><strike>EFIX DOM MAKLERSKI S.A.</strike></span>")
    firms, report = build(_fetched(brokerage_houses=_list("brokerage_houses", rec)),
                          previous={normalize_name("EFIX DOM MAKLERSKI S.A."): old_id})
    assert firms[0].id == old_id and report.renamed == [("EFIX DOM MAKLERSKI S.A.", "CERES DOM INWESTYCYJNY S.A.")]


def test_rename_without_previous_csv_gets_the_new_name_id():
    rec = _record("<span>CERES DOM INWESTYCYJNY S.A.<br /><strike>EFIX DOM MAKLERSKI S.A.</strike></span>")
    firms, report = build(_fetched(brokerage_houses=_list("brokerage_houses", rec)))
    assert firms[0].id == firm_id("CERES DOM INWESTYCYJNY S.A.") and report.renamed == []


def test_carried_id_never_collides_with_a_current_firm():
    # The old name is still a firm of its own, so its id is taken and not carried over.
    a = _record("<span>New Name Ltd<br /><strike>Old Name Ltd</strike></span>")
    b = _record("Old Name Ltd")
    firms, report = build(_fetched(no_branch=_list("no_branch", a, b)),
                          previous={normalize_name("Old Name Ltd"): firm_id("Old Name Ltd")})
    assert len({f.id for f in firms}) == 2 and report.renamed == []


def test_bank_former_name_joined_like_the_name_is_carried():
    old = "SANTANDER BANK POLSKA S.A. – Santander Biuro Maklerskie"
    rec = _record("<span><strike>SANTANDER BANK POLSKA S.A.<br />Santander Biuro Maklerskie</strike><br />"
                  "ERSTE BANK POLSKA S.A.<br />Erste Biuro Maklerskie</span>")
    firms, _ = build(_fetched(banks=_list("banks", rec)), previous={normalize_name(old): firm_id(old)})
    assert firms[0].id == firm_id(old) and firms[0].name == "ERSTE BANK POLSKA S.A. – Erste Biuro Maklerskie"


# ---- one firm per name -------------------------------------------------------------------------------


def test_duplicate_name_in_one_list_is_one_firm_with_merged_aliases_and_domains():
    a = _record("GBR Capital GmbH", Dodatkowe_informacje="nazwa handlowa: GBRX, www.gbr-one.example")
    b = _record("GBR Capital GmbH", Dodatkowe_informacje="nazwa handlowa: GBRZ, www.gbr-two.example")
    firms, report = build(_fetched(no_branch=_list("no_branch", a, b)))
    (f,) = firms
    assert {"GBRX", "GBRZ"} <= set(f.aliases) and f.domains == ["gbr-one.example", "gbr-two.example"]
    assert report.merged_same_list == ["GBR Capital GmbH"]


def test_same_firm_on_two_lists_takes_the_branch_type_and_url():
    rec = _record("IG Europe GmbH", Państwo_macierzyste="Niemcy")
    firms, report = build(_fetched(no_branch=_list("no_branch", rec), branches=_list("branches", rec)))
    (f,) = firms
    assert (f.type, f.source_url, f.country) == ("foreign_branch", SOURCES["branches"].url, "DE")
    assert report.merged_across_lists == ["IG Europe GmbH"]


def test_same_core_different_legal_names_are_two_firms_without_the_shared_core():
    firms, report = build(_fetched(no_branch=_list("no_branch", _record("Alpha Capital Ltd"),
                                                    _record("Alpha Capital GmbH"))))
    assert len({f.id for f in firms}) == 2
    assert all("Alpha Capital" not in f.aliases for f in firms)
    assert sum(1 for _, a, r in report.dropped_aliases if a == "Alpha Capital" and r == "shared") == 2


# ---- aliases ----------------------------------------------------------------------------------------


def test_bank_brokerage_unit_and_abbreviation(built):
    pko = _firm(built[0], "POWSZECHNA KASA OSZCZĘDNOŚCI BANK POLSKI S.A. (PKO BP S.A.) – "
                          "Biuro Maklerskie PKO Banku Polskiego")
    assert {"PKO BP", "Biuro Maklerskie PKO Banku Polskiego"} <= set(pko.aliases)
    assert pko.type == "brokerage_bank" and pko.country == "PL"


def test_brokerage_house_dm_and_case_forms(built):
    cvi = _firm(built[0], "CVI DOM MAKLERSKI SP. Z O.O.")
    assert {"CVI DOM MAKLERSKI", "DM CVI", "CVI DM", "domu maklerskiego CVI"} <= set(cvi.aliases)


def test_former_names_are_aliases_with_their_legal_form(built):
    ceres = _firm(built[0], "CERES DOM INWESTYCYJNY S.A.")
    assert "EFIX DOM MAKLERSKI S.A." in ceres.aliases and "EFIX DOM MAKLERSKI" in ceres.aliases


def test_trade_names_split_and_without_domains(built):
    abf = _firm(built[0], "ABF TRADE EU LIMITED")
    assert {"AccurateFX", "XGLOBAL", "AHMZTradeFX"} <= set(abf.aliases)
    assert not any("." in a.rstrip(".") and " " not in a for a in abf.aliases)


def test_trade_names_parser():
    assert trade_names("Nazwy handlowe: AccurateFX XGLOBAL AHMZTradeFX abftrade.com/eu") == [
        "AccurateFX", "XGLOBAL", "AHMZTradeFX"]
    assert trade_names("nazwy handlowe: 50K, 50Coins www.50k.trade [od 10.05.2024]") == ["50K", "50Coins"]
    assert trade_names("nazwa handlowa: Doo Financial") == ["Doo Financial"]
    assert trade_names("nazwa handlowa: SOHO MARKETS http://vestofx.com/eu") == ["SOHO MARKETS"]
    assert trade_names("nazwa handlowa: Emporium Capital od 14.10.2022: www.ecgprime.com") == ["Emporium Capital"]
    assert trade_names("OTF: FTFS MTF: FTFS") == []


def test_generic_and_short_aliases_dropped_full_name_kept(built):
    firms, report = built
    dropped = {(n, a): r for n, a, r in report.dropped_aliases}
    assert dropped[("AC Markets (Europe) Ltd", "Europe")] == "generic"
    assert dropped[("XSpot Wealth (EU) Ltd", "EU")] == "too_short"
    assert _firm(firms, "AC Markets (Europe) Ltd")


def test_short_brands_are_kept(built):
    firms = built[0]
    assert "XTB" in _firm(firms, "XTB S.A.").aliases
    assert "mBANK" in _firm(firms, "mBANK S.A. – Biuro Maklerskie mBank").aliases
    assert "EXT" in _firm(firms, "EXT Ltd").aliases


def test_shared_alias_stays_with_the_polish_firm(built):
    firms, report = built
    assert "XTB" in _firm(firms, "XTB S.A.").aliases and "XTB" not in _firm(firms, "XTB Ltd").aliases
    assert ("XTB Ltd", "XTB", "shared") in report.dropped_aliases
    assert ("XTB S.A.", "XTB", "shared") not in report.dropped_aliases


def test_translation_line_is_an_alias_not_part_of_the_name():
    rec = _record("<span>Bitstamp finančne storitve d.o.o.<br />(ang. Bitstamp Financial Services Ltd.)</span>",
                  Państwo_macierzyste="Słowenia")
    (f,), _ = build(_fetched(no_branch=_list("no_branch", rec)))
    assert f.name == "Bitstamp finančne storitve d.o.o." and f.country == "SI"
    assert "Bitstamp Financial Services Ltd." in f.aliases


def test_alias_never_repeats_the_name_or_itself(built):
    for f in built[0]:
        keys = [normalize_name(a) for a in f.aliases]
        assert len(keys) == len(set(keys)) and normalize_name(f.name) not in keys, f.name


# ---- domains ----------------------------------------------------------------------------------------


def test_domains_from_notes_without_struck_ones(built):
    assert _firm(built[0], "50KCY LTD").domains == ["50k.trade"]
    assert _firm(built[0], "XTB Ltd").domains == ["xtb.com"]


def test_supervisor_site_is_never_a_firm_domain():
    a = _record("Cy Firm Ltd", Organ_nadzoru="www.cysec.gov.cy", Dodatkowe_informacje="www.cy-firm.example")
    b = _record("Odd Firm Ltd", Dodatkowe_informacje="strona: www.cysec.gov.cy/register, www.odd.example")
    firms, report = build(_fetched(no_branch=_list("no_branch", a, b)))
    assert all("cysec.gov.cy" not in f.domains for f in firms)
    assert ("cysec.gov.cy", "supervisor") in report.dropped_domains
    assert _firm(firms, "Odd Firm Ltd").domains == ["odd.example"]


def test_social_and_shared_domains_dropped():
    a = _record("One Ltd", Dodatkowe_informacje="www.facebook.com/one www.shared.example")
    b = _record("Two Ltd", Dodatkowe_informacje="https://shared.example/two")
    firms, report = build(_fetched(no_branch=_list("no_branch", a, b)))
    assert all(f.domains == [] for f in firms)
    assert {("facebook.com", "social"), ("shared.example", "shared")} <= set(report.dropped_domains)


def test_empty_domains(built):
    assert _firm(built[0], "CERES DOM INWESTYCYJNY S.A.").domains == []
    assert all(f.domains == [] for f in built[0] if f.type in ("brokerage_house", "brokerage_bank"))


def test_domain_tokens():
    assert domains_in("www.50k.trade [od 10.05.2024] abftrade.com/eu https://www.Easy-Markets.com/ x@mail.example") \
        == ["50k.trade", "abftrade.com", "easy-markets.com"]
    assert domains_in("S.A. d.o.o. 10.05.2024 Ltd.") == []


# ---- countries --------------------------------------------------------------------------------------


def test_countries(built):
    firms, report = built
    assert _firm(firms, "Admiral Markets AS").country == "EE"
    assert all(f.country == "PL" for f in firms if f.type in ("brokerage_house", "brokerage_bank"))
    assert report.unknown_countries == []


def test_unknown_country_is_empty_and_counted():
    (f,), report = build(_fetched(no_branch=_list("no_branch", _record("Far Ltd", Państwo_macierzyste="Atlantyda"))))
    assert f.country is None and report.unknown_countries == [("Far Ltd", "Atlantyda")]


def test_record_counts(built):
    assert built[1].records == {"brokerage_houses": 28, "banks": 10, "branches": 10, "no_branch": 52}


# ---- review fixes (group 2) -------------------------------------------------------------------------


def _previous(firms) -> dict[str, str]:
    return {normalize_name(f.name): f.id for f in firms}


def test_renamed_id_survives_a_second_reload():
    old_id = firm_id("EFIX DOM MAKLERSKI S.A.")
    rec = _record("<span>CERES DOM INWESTYCYJNY S.A.<br /><strike>EFIX DOM MAKLERSKI S.A.</strike></span>")
    lists = _fetched(brokerage_houses=_list("brokerage_houses", rec))
    first, _ = build(lists, previous={normalize_name("EFIX DOM MAKLERSKI S.A."): old_id})
    second, report = build(lists, previous=_previous(first))
    third, _ = build(lists, previous=_previous(second))
    assert first[0].id == second[0].id == third[0].id == old_id
    assert report.renamed == []  # already carried, not a new rename


def test_previous_id_for_the_same_name_is_kept_even_if_uuid5_differs():
    prev = {normalize_name("XTB S.A."): "0b6d2f1e-3c4a-4b5d-8e6f-7a8b9c0d1e2f"}
    firms, _ = build(_fetched(brokerage_houses=_list("brokerage_houses", _record("XTB S.A."))), previous=prev)
    assert firms[0].id == "0b6d2f1e-3c4a-4b5d-8e6f-7a8b9c0d1e2f"


def test_carry_over_does_not_depend_on_record_order():
    a = _record("<span>Alpha One Ltd<br /><strike>Old Shared Ltd</strike></span>")
    b = _record("<span>Beta Two Ltd<br /><strike>Old Shared Ltd</strike></span>")
    prev = {normalize_name("Old Shared Ltd"): firm_id("Old Shared Ltd")}
    one, _ = build(_fetched(no_branch=_list("no_branch", a, b)), previous=prev)
    two, _ = build(_fetched(no_branch=_list("no_branch", b, a)), previous=prev)
    assert {f.name: f.id for f in one} == {f.name: f.id for f in two}
    assert sorted(f.id for f in one).count(firm_id("Old Shared Ltd")) == 1


def test_bracketed_seat_is_not_an_alias(built):
    firms, report = built
    ati = _firm(firms, "A.T.I. Associstes (Cyprus) Ltd")
    assert "Cyprus" not in ati.aliases
    assert ("A.T.I. Associstes (Cyprus) Ltd", "Cyprus", "generic") in report.dropped_aliases
    (f,), _ = build(_fetched(no_branch=_list("no_branch", _record("Airwallex Capital (Netherlands) B.V."))))
    assert "Netherlands" not in f.aliases and "Airwallex Capital" in f.aliases


def test_generic_short_core_inc_and_ambiguous_pge_dropped(built):
    firms = built[0]
    assert "INC" not in _firm(firms, "DOM MAKLERSKI INC S.A.").aliases
    assert "PGE" not in _firm(firms, "PGE DOM MAKLERSKI S.A.").aliases
    assert "PGE DOM MAKLERSKI" in _firm(firms, "PGE DOM MAKLERSKI S.A.").aliases


def test_more_legal_suffixes_stripped():
    (f,), _ = build(_fetched(no_branch=_list("no_branch", _record("Finax, o.c.p., a.s."),)))
    assert "Finax" in f.aliases and not any(a.endswith(", o.c.p") for a in f.aliases)
    (g,), _ = build(_fetched(no_branch=_list(
        "no_branch", _record("Tradition Financial Services España, Sociedad De Valores, S.A.U."))))
    assert "Tradition Financial Services España, Sociedad De Valores" in g.aliases
    assert not any(a.endswith(", U") for a in g.aliases)


def test_bank_departament_case_forms_are_clean(built):
    handlowy = [f for f in built[0] if f.name.startswith("BANK HANDLOWY")][0]
    assert "departamentu maklerskiego Banku Handlowego" in handlowy.aliases
    assert not any("maklerskiego Departament" in a for a in handlowy.aliases)


def test_supervisor_subdomain_is_never_a_firm_domain():
    a = _record("Cy Firm Ltd", Organ_nadzoru="www.cysec.gov.cy")
    b = _record("Odd Firm Ltd", Dodatkowe_informacje="rejestr: registry.cysec.gov.cy, www.odd.example")
    firms, report = build(_fetched(no_branch=_list("no_branch", a, b)))
    assert _firm(firms, "Odd Firm Ltd").domains == ["odd.example"]
    assert ("registry.cysec.gov.cy", "supervisor") in report.dropped_domains


def test_shared_domain_stays_with_the_polish_firm():
    pl = _record("XTB S.A.", Dodatkowe_informacje="www.xtb.com")
    cy = _record("XTB Ltd", Dodatkowe_informacje="www.xtb.com")
    firms, report = build(_fetched(brokerage_houses=_list("brokerage_houses", pl), no_branch=_list("no_branch", cy)))
    assert _firm(firms, "XTB S.A.").domains == ["xtb.com"] and _firm(firms, "XTB Ltd").domains == []
    assert ("xtb.com", "shared") in report.dropped_domains


def test_polish_country_name_in_brackets_is_not_an_alias():
    (f,), _ = build(_fetched(no_branch=_list("no_branch", _record("Kappa Invest (Niemcy) GmbH"))))
    assert "Niemcy" not in f.aliases


# ---- review fixes (group 5: the real snapshot) -----------------------------------------------------


def test_trade_name_in_capitals_is_never_split():
    assert trade_names("nazwa handlowa: LONDON AND CAPITAL WEALTH MANAGEMENT EUROPE") == [
        "LONDON AND CAPITAL WEALTH MANAGEMENT EUROPE"]


def test_cities_function_words_and_market_terms_are_no_aliases():
    rec = _record("W1M Europe Ltd", Dodatkowe_informacje="nazwy handlowe: London, And, Shares, Dealing, OTF, Man, Plum")
    (f,), report = build(_fetched(no_branch=_list("no_branch", rec)))
    assert not {"London", "And", "Shares", "Dealing", "OTF", "Man"} & set(f.aliases)
    assert "Plum" in f.aliases  # a real brand stays
    reasons = {a: r for _, a, r in report.dropped_aliases}
    assert reasons["London"] == "generic" and reasons["Man"] == "ambiguous"
