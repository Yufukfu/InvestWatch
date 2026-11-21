"""Generate deterministic mock data matching the v1 contracts.

All firms, people, handles and URLs are fictional. Run from any directory:

    python contracts/mocks/generate_mocks.py

Outputs JSON files next to this script (one per API response / table).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
NS = uuid.UUID("6f1c2d4e-0000-4000-8000-1a2b3c4d5e6f")
NOW = datetime(2026, 11, 21, 16, 0, tzinfo=timezone.utc)
THRESHOLDS = {"M1": 0.6, "M2": 0.5, "M3": 0.7}


def uid(name: str) -> str:
    return str(uuid.uuid5(NS, name))


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()


def risk_level(module: str, score: float) -> str:
    t = THRESHOLDS[module]
    return "high" if score >= t else "medium" if score >= t - 0.2 else "low"


# --- Sources -----------------------------------------------------------------

SOURCES = [
    dict(key="src-alfa-www", name="Alfa Inwestycje DM – strona WWW", platform="web",
         url="https://alfa-inwestycje.example.com/", source_kind="firm_own", target_modules=["M2"],
         schedule_cron="0 */6 * * *"),
    dict(key="src-eurotrade-www", name="EuroTrade Markets – promocje PL", platform="web",
         url="https://eurotrade-markets.example.com/pl/promocje", source_kind="firm_own", target_modules=["M2"],
         schedule_cron="0 */6 * * *"),
    dict(key="src-ig-hashtag", name="Instagram – #inwestowanie #forex", platform="instagram",
         url="https://www.instagram.com/explore/tags/inwestowanie/", source_kind="third_party",
         target_modules=["M1", "M3"], schedule_cron="*/30 * * * *"),
    dict(key="src-web-advisory", name="Wyszukiwanie: 'family office' / 'wealth management'", platform="web",
         url="https://search.example.com/?q=family+office+warszawa", source_kind="unknown",
         target_modules=["M3"], schedule_cron="0 * * * *"),
]

# --- Documents + findings (hand-written scenarios) ----------------------------

M2_RULE_NAMES = {
    "R1": "Identyfikacja firmy", "R2": "Oznaczenie reklamy", "R3": "Informacja o ryzyku",
    "R4": "Rozmiar czcionki ryzyka", "R5": "Ekspozycja i kontrast ryzyka", "R6": "Zakrywanie / ukrywanie ryzyka",
    "R7": "Dostępność za 1 kliknięciem", "R8": "Responsywność", "R10": "Spójność językowa",
    "R14": "Ostrzeżenie przy wynikach historycznych", "R15": "Prognozy przyszłych wyników",
    "R17": "Zakaz sugerowania aprobaty organu nadzoru", "R18": "Nadzór jako argument bezpieczeństwa",
}
LEGAL = {
    "R1": "art. 44 ust. 2 lit. a rozp. del. 2017/565", "R2": "art. 24 ust. 3 MiFID II",
    "R3": "art. 44 ust. 2 lit. b rozp. del. 2017/565", "R4": "art. 44 ust. 2 lit. c rozp. del. 2017/565",
    "R5": "art. 44 ust. 2 lit. c i e rozp. del. 2017/565", "R6": "art. 44 ust. 2 lit. e rozp. del. 2017/565",
    "R7": "art. 44 ust. 2 lit. b i e rozp. del. 2017/565", "R8": "art. 44 ust. 2 lit. g rozp. del. 2017/565",
    "R10": "art. 44 ust. 2 lit. f rozp. del. 2017/565", "R14": "art. 44 ust. 4 lit. d rozp. del. 2017/565",
    "R15": "art. 44 ust. 6 rozp. del. 2017/565", "R17": "art. 44 ust. 8 rozp. del. 2017/565",
    "R18": "art. 44 ust. 8 rozp. del. 2017/565",
}

FIRMS = {
    "alfa": dict(name="Alfa Inwestycje Dom Maklerski S.A.", registry_type="brokerage_house"),
    "eurotrade": dict(name="EuroTrade Markets Ltd (oddział w Polsce)", registry_type="foreign_branch"),
    "bank": dict(name="Bank Przykładowy S.A. – Biuro Maklerskie", registry_type="brokerage_bank"),
}


def rule(rule_id, result, severity, evidence=None, explanation=None, method="rule", name=None, legal=None):
    return dict(rule_id=rule_id, name=name or M2_RULE_NAMES[rule_id], result=result, severity=severity,
                evidence=evidence, evidence_locator=None, explanation=explanation,
                legal_basis=legal if legal is not None else LEGAL.get(rule_id), method=method)


def signal(rule_id, name, result, severity, evidence=None, explanation=None, method="rule"):
    return rule(rule_id, result, severity, evidence, explanation, method, name=name, legal=None)


SCENARIOS = [
    # ---------------- M2: firm-own marketing -------------------------------
    dict(
        key="m2-alfa-landing", source="src-alfa-www", platform="web", source_kind="firm_own", hours_ago=1,
        url="https://alfa-inwestycje.example.com/konto-premium",
        title="Konto Premium – zarabiaj do 18% rocznie",
        text=("Konto Premium Alfa Inwestycje. Zarabiaj nawet do 18% rocznie na portfelu ETF! "
              "Dołącz do 50 000 zadowolonych inwestorów. Działamy pod nadzorem KNF – Twoje środki są bezpieczne. "
              "Otwórz konto w 5 minut. *Inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału."),
        author=None,
        blocks=[
            dict(viewport="desktop", text="Zarabiaj nawet do 18% rocznie na portfelu ETF!", tag="h1", font_size_px=44,
                 font_weight=700, color="#111111", background_color="#ffffff", bbox=[80, 120, 900, 60], visible=True,
                 in_viewport_on_load=True, requires_interaction=False, region="main", overflow_clipped=False),
            dict(viewport="desktop", text="Działamy pod nadzorem KNF – Twoje środki są bezpieczne.", tag="p",
                 font_size_px=20, font_weight=400, color="#222222", background_color="#ffffff",
                 bbox=[80, 200, 700, 28], visible=True, in_viewport_on_load=True, requires_interaction=False,
                 region="main", overflow_clipped=False),
            dict(viewport="desktop", text="*Inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału.",
                 tag="small", font_size_px=9, font_weight=400, color="#bbbbbb", background_color="#ffffff",
                 bbox=[80, 2400, 600, 12], visible=True, in_viewport_on_load=False, requires_interaction=False,
                 region="footer", overflow_clipped=False),
            dict(viewport="mobile", text="*Inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału.",
                 tag="small", font_size_px=8, font_weight=400, color="#bbbbbb", background_color="#ffffff",
                 bbox=[16, 3900, 340, 30], visible=True, in_viewport_on_load=False, requires_interaction=False,
                 region="footer", overflow_clipped=True),
        ],
        finding=dict(
            module="M2", score=0.86, status="new", firm="alfa",
            title="Obietnica 18% zysku z ostrzeżeniem o ryzyku ukrytym w stopce",
            summary=("Materiał eksponuje stopę zwrotu 18% i powołuje się na nadzór KNF jako gwarancję bezpieczeństwa. "
                     "Ostrzeżenie o ryzyku jest w stopce, czcionką 9 px w jasnoszarym kolorze."),
            rules=[
                rule("R1", "pass", "medium", "Konto Premium Alfa Inwestycje", "Nazwa firmy jest podana."),
                rule("R2", "fail", "medium", None, "Brak oznaczenia materiału jako reklamy."),
                rule("R3", "fail", "high", "Zarabiaj nawet do 18% rocznie na portfelu ETF!",
                     "Obietnica zysku bez ostrzeżenia o ryzyku w bezpośrednim sąsiedztwie.", "hybrid"),
                rule("R4", "fail", "medium", "*Inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału.",
                     "Ostrzeżenie 9 px przy przeważającej czcionce 20 px (0,45×)."),
                rule("R5", "fail", "medium", None, "Kontrast ostrzeżenia 1,9:1 (wymagane min. 4,5:1)."),
                rule("R6", "fail", "high", None, "Ostrzeżenie wyłącznie w stopce, niewidoczne bez przewijania."),
                rule("R8", "fail", "low", None, "Na telefonie ostrzeżenie ma 8 px i jest ucięte."),
                rule("R10", "pass", "low"),
                rule("R17", "fail", "high", "Działamy pod nadzorem KNF – Twoje środki są bezpieczne.",
                     "Odwołanie do KNF sugeruje aprobatę produktu.", "llm"),
                rule("R18", "fail", "high", "Działamy pod nadzorem KNF – Twoje środki są bezpieczne.",
                     "Nadzór KNF użyty jako argument bezpieczeństwa inwestycji.", "llm"),
            ],
        ),
    ),
    dict(
        key="m2-eurotrade-bonus", source="src-eurotrade-www", platform="web", source_kind="firm_own", hours_ago=5,
        url="https://eurotrade-markets.example.com/pl/promocje/bonus-cfd",
        title="Bonus 500 zł na start z CFD",
        text=("Handluj CFD na indeksy z bonusem 500 zł na start! Nasi klienci zarobili średnio 34% w 2025 roku. "
              "W przyszłym roku spodziewamy się jeszcze lepszych wyników. "
              "Risk warning: CFDs are complex instruments and come with a high risk of losing money rapidly due to leverage."),
        author=None,
        blocks=[
            dict(viewport="desktop", text="Nasi klienci zarobili średnio 34% w 2025 roku.", tag="h2", font_size_px=36,
                 font_weight=700, color="#0a0a0a", background_color="#ffe600", bbox=[60, 300, 800, 48], visible=True,
                 in_viewport_on_load=True, requires_interaction=False, region="main", overflow_clipped=False),
            dict(viewport="desktop", text="Risk warning: CFDs are complex instruments and come with a high risk of losing money rapidly due to leverage.",
                 tag="p", font_size_px=14, font_weight=400, color="#333333", background_color="#ffffff",
                 bbox=[60, 380, 900, 20], visible=False, in_viewport_on_load=False, requires_interaction=True,
                 region="main", overflow_clipped=False),
        ],
        finding=dict(
            module="M2", score=0.74, status="in_review", firm="eurotrade",
            title="Wyniki historyczne i prognoza bez ostrzeżenia; ryzyko po angielsku za kliknięciem",
            summary=("Reklama CFD eksponuje wynik 34% za 2025 r. i zapowiada lepsze wyniki. Ostrzeżenie o ryzyku "
                     "jest po angielsku i widoczne dopiero po rozwinięciu sekcji."),
            rules=[
                rule("R1", "pass", "medium", "EuroTrade Markets"),
                rule("R3", "uncertain", "high", None, "Ostrzeżenie istnieje, ale nie towarzyszy bezpośrednio obietnicy zysku.", "llm"),
                rule("R7", "fail", "medium", None, "Ostrzeżenie widoczne dopiero po rozwinięciu sekcji."),
                rule("R10", "fail", "medium", "Risk warning: CFDs are complex instruments",
                     "Ostrzeżenie w języku angielskim, główny przekaz po polsku."),
                rule("R14", "fail", "high", "Nasi klienci zarobili średnio 34% w 2025 roku.",
                     "Brak zastrzeżenia, że wyniki historyczne nie są wiarygodnym wskaźnikiem przyszłych wyników."),
                rule("R15", "fail", "medium", "W przyszłym roku spodziewamy się jeszcze lepszych wyników.",
                     "Prognoza bez wymaganego ostrzeżenia.", "llm"),
            ],
        ),
    ),
    dict(
        key="m2-bank-ok", source=None, platform="web", source_kind="firm_own", hours_ago=9,
        url="https://bank-przykladowy.example.com/maklerskie/ike",
        title="IKE w Biurze Maklerskim",
        text=("Reklama. Bank Przykładowy S.A. – Biuro Maklerskie. Otwórz IKE i inwestuj długoterminowo. "
              "Inwestowanie w instrumenty finansowe wiąże się z ryzykiem utraty części lub całości zainwestowanego kapitału. "
              "Traktowanie podatkowe zależy od indywidualnej sytuacji klienta i może ulec zmianie."),
        author=None, blocks=[],
        finding=dict(
            module="M2", score=0.12, status="closed", firm="bank",
            title="Materiał IKE – wymogi spełnione",
            summary="Materiał oznaczony jako reklama, z wyraźnym ostrzeżeniem o ryzyku i zastrzeżeniem podatkowym.",
            rules=[
                rule("R1", "pass", "medium", "Bank Przykładowy S.A. – Biuro Maklerskie"),
                rule("R2", "pass", "medium", "Reklama."),
                rule("R3", "pass", "high", "Inwestowanie w instrumenty finansowe wiąże się z ryzykiem utraty części lub całości zainwestowanego kapitału."),
                rule("R4", "not_applicable", "medium", None, "Brak danych o renderowaniu strony."),
                rule("R6", "not_applicable", "high", None, "Brak danych o renderowaniu strony."),
            ],
        ),
    ),
    # ---------------- M1: finfluencers / third parties ----------------------
    dict(
        key="m1-ig-jan", source="src-ig-hashtag", platform="instagram", source_kind="third_party", hours_ago=2,
        url="https://www.instagram.com/p/MOCK0001/",
        title=None,
        text=("Od pół roku gram na forexie w EuroTrade Markets i to najlepsza decyzja w moim życiu 🚀 "
              "Z moim linkiem dostaniesz bonus 500 zł na start – link w bio! #forex #inwestowanie #pasywnydochod"),
        author=dict(name="Jan Inwestor", handle="@inwestor_jan", profile_url="https://www.instagram.com/inwestor_jan/",
                    followers=48200),
        links=[dict(href="https://eurotrade-markets.example.com/pl/register?ref=JAN500", text="link w bio", rel=None)],
        blocks=[],
        finding=dict(
            module="M1", score=0.91, status="new", firm="eurotrade",
            advertiser=dict(name="Jan Inwestor", handle="@inwestor_jan",
                            profile_url="https://www.instagram.com/inwestor_jan/", in_registry=False),
            title="Finfluencer @inwestor_jan reklamuje EuroTrade Markets z linkiem afiliacyjnym",
            summary=("Post promuje konto w EuroTrade Markets z kodem polecającym JAN500. Brak oznaczenia współpracy "
                     "i jakiejkolwiek informacji o ryzyku."),
            rules=[
                signal("S1.1", "Wzmianka o firmie z rejestru", "fail", "medium", "EuroTrade Markets"),
                signal("S1.2", "Link afiliacyjny / kod polecający", "fail", "high", "register?ref=JAN500"),
                signal("S1.3", "Oznaczenie współpracy", "pass", "medium", None, "Brak #reklama / #współpraca."),
                signal("S1.4", "Wezwanie do działania", "fail", "medium", "link w bio!"),
                signal("S1.5", "Treść promocyjna", "fail", "high", "to najlepsza decyzja w moim życiu", method="llm"),
                signal("S1.6", "Autor inny niż firma", "fail", "medium", "@inwestor_jan"),
            ],
        ),
    ),
    dict(
        key="m1-ig-kasia", source="src-ig-hashtag", platform="instagram", source_kind="third_party", hours_ago=7,
        url="https://www.instagram.com/p/MOCK0002/",
        title=None,
        text=("#współpraca z Alfa Inwestycje DM. Pokazuję, jak założyłam rachunek maklerski i kupiłam pierwszy ETF. "
              "Pamiętajcie: inwestowanie wiąże się z ryzykiem, możecie stracić część pieniędzy."),
        author=dict(name="Finanse z Kasią", handle="@finanse_z_kasia",
                    profile_url="https://www.instagram.com/finanse_z_kasia/", followers=125000),
        links=[], blocks=[],
        finding=dict(
            module="M1", score=0.64, status="confirmed", firm="alfa",
            advertiser=dict(name="Finanse z Kasią", handle="@finanse_z_kasia",
                            profile_url="https://www.instagram.com/finanse_z_kasia/", in_registry=False),
            title="Oznaczona współpraca @finanse_z_kasia z Alfa Inwestycje DM",
            summary="Post oznaczony jako współpraca, zawiera ostrzeżenie o ryzyku. Do ewidencji współprac firmy.",
            rules=[
                signal("S1.1", "Wzmianka o firmie z rejestru", "fail", "medium", "Alfa Inwestycje DM"),
                signal("S1.3", "Oznaczenie współpracy", "fail", "medium", "#współpraca"),
                signal("S1.5", "Treść promocyjna", "fail", "medium", "jak założyłam rachunek maklerski", method="llm"),
                signal("S1.6", "Autor inny niż firma", "fail", "medium", "@finanse_z_kasia"),
            ],
        ),
    ),
    dict(
        key="m1-ig-edu", source="src-ig-hashtag", platform="instagram", source_kind="third_party", hours_ago=20,
        url="https://www.instagram.com/p/MOCK0003/",
        title=None,
        text="Czym różni się ETF akumulujący od dystrybuującego? Krótki poradnik bez polecania konkretnych biur maklerskich.",
        author=dict(name="Ekonomia na luzie", handle="@ekonomia_na_luzie",
                    profile_url="https://www.instagram.com/ekonomia_na_luzie/", followers=9100),
        links=[], blocks=[],
        finding=dict(
            module="M1", score=0.18, status="false_positive", firm=None,
            advertiser=dict(name="Ekonomia na luzie", handle="@ekonomia_na_luzie",
                            profile_url="https://www.instagram.com/ekonomia_na_luzie/", in_registry=False),
            title="Treść edukacyjna o ETF – brak reklamy firmy",
            summary="Materiał edukacyjny bez wskazania firmy inwestycyjnej i bez linków.",
            rules=[
                signal("S1.1", "Wzmianka o firmie z rejestru", "pass", "medium"),
                signal("S1.5", "Treść promocyjna", "pass", "high", None, "Treść edukacyjna.", "llm"),
            ],
        ),
    ),
    # ---------------- M3: shadow advisory ------------------------------------
    dict(
        key="m3-zloty-kapital", source="src-web-advisory", platform="web", source_kind="unknown", hours_ago=3,
        url="https://zlotykapital-fo.example.com/oferta",
        title="ZłotyKapitał Family Office – indywidualna strategia",
        text=("ZłotyKapitał Family Office. Po bezpłatnej konsultacji 1:1 dopasujemy portfel do Twojej sytuacji. "
              "W tym kwartale rekomendujemy kupno obligacji skarbowych i akcji spółek z WIG20 oraz sprzedaż ETF na złoto. "
              "Abonament 990 zł miesięcznie."),
        author=None, blocks=[],
        finding=dict(
            module="M3", score=0.93, status="new", firm=None,
            advertiser=dict(name="ZłotyKapitał Family Office", website="https://zlotykapital-fo.example.com/",
                            in_registry=False, on_warning_list=False),
            title="Podmiot spoza rejestru rekomenduje kupno i sprzedaż konkretnych instrumentów",
            summary=("Oferta zawiera spersonalizowane rekomendacje nabycia i zbycia instrumentów finansowych "
                     "(obligacje, akcje WIG20, ETF) za opłatą. Podmiot nie występuje w rejestrze firm inwestycyjnych KNF."),
            rules=[
                signal("S3.1", "Podmiot spoza rejestru", "fail", "high", "ZłotyKapitał Family Office"),
                signal("S3.2", "Słownictwo usług doradczych", "fail", "medium", "Family Office"),
                signal("S3.3", "Personalizacja", "fail", "high", "dopasujemy portfel do Twojej sytuacji", method="llm"),
                signal("S3.4", "Rekomendacja konkretnych instrumentów", "fail", "high",
                       "rekomendujemy kupno obligacji skarbowych i akcji spółek z WIG20 oraz sprzedaż ETF na złoto", method="llm"),
                signal("S3.5", "Model odpłatny", "fail", "medium", "Abonament 990 zł miesięcznie"),
                signal("S3.6", "Kierowanie do Polski", "fail", "low", "990 zł"),
            ],
        ),
    ),
    dict(
        key="m3-sygnaly-vip", source="src-ig-hashtag", platform="instagram", source_kind="third_party", hours_ago=11,
        url="https://www.instagram.com/p/MOCK0004/",
        title=None,
        text=("Grupa VIP – sygnały premium na akcje i CFD. Codziennie mówię, co kupić, a co sprzedać. "
              "Ostatni miesiąc +27%! Dołącz za 199 zł/mies."),
        author=dict(name="Sygnały VIP", handle="@sygnaly_vip", profile_url="https://www.instagram.com/sygnaly_vip/",
                    followers=31000),
        links=[], blocks=[],
        finding=dict(
            module="M3", score=0.81, status="in_review", firm=None,
            advertiser=dict(name="Sygnały VIP", handle="@sygnaly_vip",
                            profile_url="https://www.instagram.com/sygnaly_vip/", in_registry=False,
                            on_warning_list=None),
            title="Płatne sygnały kup/sprzedaj na akcje i CFD od @sygnaly_vip",
            summary="Odpłatne rekomendacje kupna i sprzedaży instrumentów finansowych przez podmiot spoza rejestru.",
            rules=[
                signal("S3.1", "Podmiot spoza rejestru", "fail", "high", "@sygnaly_vip"),
                signal("S3.3", "Personalizacja", "pass", "high", None, "Rekomendacje masowe, niespersonalizowane.", "llm"),
                signal("S3.4", "Rekomendacja konkretnych instrumentów", "fail", "high",
                       "Codziennie mówię, co kupić, a co sprzedać.", method="llm"),
                signal("S3.5", "Model odpłatny", "fail", "medium", "Dołącz za 199 zł/mies."),
            ],
        ),
    ),
    dict(
        key="m3-blog-edu", source="src-web-advisory", platform="web", source_kind="unknown", hours_ago=26,
        url="https://blog-finansowy.example.com/czym-jest-family-office",
        title="Czym jest family office?",
        text="Wyjaśniamy, czym jest family office i jak wybrać licencjonowanego doradcę. Nie udzielamy rekomendacji inwestycyjnych.",
        author=None, blocks=[],
        finding=dict(
            module="M3", score=0.22, status="false_positive", firm=None,
            advertiser=dict(name="Blog finansowy", website="https://blog-finansowy.example.com/", in_registry=False),
            title="Artykuł edukacyjny o family office",
            summary="Brak rekomendacji instrumentów i personalizacji – treść informacyjna.",
            rules=[
                signal("S3.1", "Podmiot spoza rejestru", "fail", "high", "Blog finansowy"),
                signal("S3.2", "Słownictwo usług doradczych", "fail", "medium", "family office"),
                signal("S3.4", "Rekomendacja konkretnych instrumentów", "pass", "high", None,
                       "Brak rekomendacji instrumentów.", "llm"),
            ],
        ),
    ),
]


def build():
    sources, documents, findings = [], [], []

    for s in SOURCES:
        sources.append(dict(
            id=uid(s["key"]), name=s["name"], platform=s["platform"], url=s["url"], source_kind=s["source_kind"],
            target_modules=s["target_modules"], schedule_cron=s["schedule_cron"], active=True,
            last_run_at=iso(NOW - timedelta(minutes=25)), last_run_status="ok", documents_count=None,
        ))

    for sc in SCENARIOS:
        doc_id = uid("doc-" + sc["key"])
        fetched = NOW - timedelta(hours=sc["hours_ago"])
        has_blocks = bool(sc.get("blocks"))
        documents.append(dict(
            id=doc_id,
            source_id=uid(sc["source"]) if sc["source"] else None,
            platform=sc["platform"], source_kind=sc["source_kind"], url=sc["url"], canonical_url=sc["url"],
            fetched_at=iso(fetched), published_at=iso(fetched - timedelta(hours=3)), http_status=200, lang="pl",
            title=sc["title"], text=sc["text"], content_hash=sha(sc["text"]), author=sc.get("author"),
            links=sc.get("links", []), media=[],
            html_object_key=f"html/{doc_id}.html" if sc["platform"] == "web" else None,
            screenshots=({"desktop": f"shot/{doc_id}/desktop.png", "tablet": f"shot/{doc_id}/tablet.png",
                          "mobile": f"shot/{doc_id}/mobile.png"} if has_blocks else None),
            blocks=sc.get("blocks", []),
            scrape_meta=dict(scraper="playwright" if sc["platform"] == "web" else "api",
                             user_agent="Mozilla/5.0 (mock)", proxy=None, duration_ms=1500),
        ))

        f = sc["finding"]
        firm = None
        if f.get("firm"):
            fd = FIRMS[f["firm"]]
            firm = dict(name=fd["name"], registry_id=uid("firm-" + f["firm"]), registry_type=fd["registry_type"],
                        authorized=True, match_confidence=0.95)
        detected = fetched + timedelta(seconds=40)
        findings.append(dict(
            id=uid("finding-" + sc["key"]), document_id=doc_id, module=f["module"], score=f["score"],
            risk_level=risk_level(f["module"], f["score"]), status=f["status"], title=f["title"],
            summary=f["summary"], firm=firm, advertiser=f.get("advertiser"), rules=f["rules"],
            content_excerpt=sc["text"][:200], url=sc["url"], platform=sc["platform"], note=None,
            detected_at=iso(detected), updated_at=iso(detected),
            model=dict(pipeline_version="0.1.0-mock", llm="gemma3:4b", embedder="bge-m3"),
        ))

    for s in sources:
        s["documents_count"] = sum(1 for d in documents if d["source_id"] == s["id"])

    findings.sort(key=lambda x: x["detected_at"], reverse=True)
    return sources, documents, findings


def trend(findings):
    points = []
    start = NOW.replace(minute=0, second=0) - timedelta(hours=23)
    for i in range(24):
        t = start + timedelta(hours=i)
        # background noise so the chart is not flat, plus the real mock findings
        base = {"M1": (i * 7) % 4, "M2": (i * 5) % 3, "M3": (i * 3) % 2}
        for f in findings:
            ft = datetime.strptime(f["detected_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if t <= ft < t + timedelta(hours=1):
                base[f["module"]] += 1
        points.append(dict(t=iso(t), **base))
    return dict(bucket="hour", points=points)


def calibration(module: str):
    # synthetic gold set: (score, is_violation)
    import random
    rnd = random.Random(module)
    samples = [(min(1, max(0, rnd.gauss(0.75, 0.15))), True) for _ in range(30)] + \
              [(min(1, max(0, rnd.gauss(0.35, 0.15))), False) for _ in range(40)]
    points = []
    for k in range(5, 100, 5):
        th = k / 100
        tp = sum(1 for s, y in samples if s >= th and y)
        fp = sum(1 for s, y in samples if s >= th and not y)
        fn = sum(1 for s, y in samples if s < th and y)
        tn = sum(1 for s, y in samples if s < th and not y)
        p = tp / (tp + fp) if tp + fp else 1.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        points.append(dict(threshold=th, tp=tp, fp=fp, fn=fn, tn=tn,
                           precision=round(p, 3), recall=round(r, 3), f1=round(f1, 3)))
    return dict(module=module, current_threshold=THRESHOLDS[module], labeled_samples=len(samples), points=points)


def events(findings):
    out = []
    for f in findings[:3]:
        brief = dict(id=f["id"], module=f["module"], score=f["score"], risk_level=f["risk_level"],
                     title=f["title"], url=f["url"], platform=f["platform"])
        out.append(dict(type="finding.created", emitted_at=f["detected_at"], data=brief))
        if f["risk_level"] == "high":
            out.append(dict(type="finding.high_risk", emitted_at=f["detected_at"], data=brief))
    out.append(dict(type="finding.updated", emitted_at=iso(NOW), data=dict(id=findings[1]["id"], status="in_review")))
    out.append(dict(type="scan.started", emitted_at=iso(NOW - timedelta(minutes=26)),
                    data=dict(source_id=uid("src-ig-hashtag"), documents=None, status=None)))
    out.append(dict(type="scan.finished", emitted_at=iso(NOW - timedelta(minutes=25)),
                    data=dict(source_id=uid("src-ig-hashtag"), documents=4, status="ok")))
    return out


def write(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    sources, documents, findings = build()
    docs_by_id = {d["id"]: d for d in documents}

    write("sources.json", dict(items=sources))
    write("documents.json", documents)
    write("findings.json", dict(items=findings, total=len(findings), page=1, page_size=50))

    detail = dict(findings[0])
    detail["document"] = docs_by_id[detail["document_id"]]
    detail["screenshot_urls"] = {vp: f"/api/documents/{detail['document_id']}/screenshot/{vp}"
                                 for vp in ("desktop", "tablet", "mobile")}
    write("finding-detail.json", detail)

    write("trend.json", trend(findings))
    summary = dict(
        total=len(findings),
        by_module={m: sum(1 for f in findings if f["module"] == m) for m in ("M1", "M2", "M3")},
        by_status={s: sum(1 for f in findings if f["status"] == s)
                   for s in ("new", "in_review", "confirmed", "false_positive", "closed")},
        by_platform={p: sum(1 for f in findings if f["platform"] == p) for p in sorted({f["platform"] for f in findings})},
        by_risk_level={r: sum(1 for f in findings if f["risk_level"] == r) for r in ("high", "medium", "low")},
        last_scan_at=iso(NOW - timedelta(minutes=25)),
    )
    write("summary.json", summary)
    for m in ("M1", "M2", "M3"):
        write(f"calibration-{m}.json", calibration(m))
    write("thresholds.json", THRESHOLDS)
    write("health.json", dict(status="ok", services=dict(api="ok", postgres="ok", redis="ok", minio="ok",
                                                         analytics="ok", scraper="ok", llm="ok")))
    write("events.json", events(findings))
    print(f"Wrote mocks to {OUT}")


if __name__ == "__main__":
    main()
