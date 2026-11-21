"""KNF firm registry: CSV loader and document-to-firm matching (`.docs/analytics-plan.md` §2 step 3, §3).

Per firm, the strongest signal: name or alias in the text (0.95), page host equal to or a
subdomain of a firm domain (0.9), fuzzy match of the name core on word n-grams (ratio x 0.85,
only at ratio >= 88, which for short names means an exact word anyway).
Across firms: the firm whose domain hosts the page wins (a firm's own page that names a partner
firm is still that firm's page), then the highest confidence, then the earliest and the longest quote.
Name matches quote the ORIGINAL text, so the quote can serve as rule evidence.

Names are compared on the folded text (NFKC, invisible characters removed, the first SCAN_MAX characters;
change `analytics-m1-m3`, #35 review 2) and quoted from the original through an index map.

At the size of the real KNF register (~750 firms, change `analytics-knf-registry` design decision 9): a token
index picks the firms whose name forms can occur in the text before any regex runs; a short word (one token,
fewer than 8 letters: `XTB`, `Nova`) matches only capitalized (`bossa nova` is no firm) and never fuzzily; a
form shared by several firms belongs only to the single firm of the highest type precedence.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from rapidfuzz import fuzz, process

from .models import UUID_PATTERN

FIRM_TYPES = {"brokerage_house", "brokerage_bank", "foreign_branch", "foreign_no_branch"}
#: Strongest presence in Poland first; decides who owns a name form several firms share.
TYPE_PRECEDENCE = ("brokerage_house", "brokerage_bank", "foreign_branch", "foreign_no_branch")
REQUIRED_COLUMNS = ("id", "name", "type")
#: A bank and its brokerage unit are one KNF record: `mBANK S.A. – Biuro Maklerskie mBank`.
NAME_SEPARATOR = " – "

NAME_CONFIDENCE = 0.95
DOMAIN_CONFIDENCE = 0.9
LINK_CONFIDENCE = 0.9  # a link to a firm domain in third-party content (change analytics-m1-m3)
FUZZY_FACTOR = 0.85
FUZZY_MIN_RATIO = 88
SHORT_WORD_LETTERS = 8
ACRONYM_LETTERS = 3

# Legal forms seen on the KNF lists (evidence.md, Names). Unambiguous ones are removed anywhere; short ones
# that are also words (`AS`, `SE`, `AB`) only at the end of the name.
_LEGAL_FORMS = re.compile(
    r"\(oddział w polsce\)|oddział w polsce|biuro maklerskie|departament maklerski|dom maklerski|"
    r"spółka akcyjna|\bs\.\s?a\.(?:u\.)?|"
    r"\bsp\.\s?z\s?o\.\s?o\.|\bsp\.\s?k\.|\bltd\b\.?|\blimited\b|\bllc\b|\bplc\b|\bgmbh\b|\bs\.r\.o\.|"
    r"\ba\.s\.|\bb\.v\.|\bn\.v\.|\bs\.p\.a\.|\bs\.à\s?r\.l\.|\bd\.o\.o\.|\bo\.c\.p\.|\bdm\b|"
    r"\bw restrukturyzacji\b|\bw likwidacji\b",
    re.IGNORECASE,
)
_TRAILING_FORMS = re.compile(r"[\s,]+(?:ag|se|sas|s\.a\.s\.|as|asa|a/s|ab|oy|ood|s\.l\.|sa|spa|bv|nv|uab|kft|zrt|nyrt)\.?$",
                             re.IGNORECASE)
_WORD = re.compile(r"\w+", re.UNICODE)
#: Platform hosts: a page, profile or link there is the platform's, never a firm's own domain.
SOCIAL_HOSTS = (
    "instagram.com", "facebook.com", "fb.com", "tiktok.com", "youtube.com", "youtu.be", "x.com",
    "twitter.com", "t.me", "telegram.me", "linkedin.com", "threads.net",
)
_PUNCT = re.compile(r"[^\w\s\-–]+")


class RegistryError(ValueError):
    pass


def core_name(name: str) -> str:
    """Firm name without legal-form words, e.g. 'Alfa Inwestycje Dom Maklerski S.A.' -> 'Alfa Inwestycje',
    'Admiral Markets AS' -> 'Admiral Markets'."""
    stripped = re.sub(r"\s+", " ", _LEGAL_FORMS.sub(" ", name)).strip(" -–,.")
    previous = None
    while previous != stripped:
        previous, stripped = stripped, _TRAILING_FORMS.sub("", stripped).strip(" -–,.")
    return stripped


#: Invisible characters a scraped text may hide inside a name (zero-width space, joiners, word joiner, BOM, soft
#: hyphen); they are dropped before names are compared (#35 review 2).
_INVISIBLE = frozenset("​‌‍⁠﻿­")
#: Name lookups read at most this prefix of a text (#35 review 2): NFKC can expand a character ('ﬁ' -> 'fi'), so
#: folding a 2 MB page would cost seconds and tens of MB. A prefix keeps every quote a substring of the original.
SCAN_MAX = 200_000


@lru_cache(maxsize=4)
def fold(text: str) -> tuple[str, tuple[int, ...]]:
    """NFKC per character with invisible characters removed, and for each folded character its index in `text`.

    Names are compared on the folded text (so a fullwidth or zero-width variant still matches by name) while every
    quote is cut from the original text through the index map, so evidence stays a verbatim substring.
    """
    out: list[str] = []
    where: list[int] = []
    for i, c in enumerate(text):
        if c in _INVISIBLE:
            continue
        folded = unicodedata.normalize("NFKC", c) if not c.isascii() else c
        out.append(folded)
        where.extend([i] * len(folded))
    return "".join(out), tuple(where)


def _fold_form(form: str) -> str:
    """`fold` for a short name form, without touching the small cache kept for document texts."""
    return "".join(unicodedata.normalize("NFKC", c) for c in form if c not in _INVISIBLE)


def _alias_pattern(alias: str) -> re.Pattern:
    body = r"\s+".join(re.escape(t) for t in _fold_form(alias).split())
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def _casefold(word: str) -> str:
    """casefold, with the Turkish dotted and dotless i read as `i`, as `re.IGNORECASE` does."""
    return word.casefold().replace("i̇", "i").replace("ı", "i")


def _form_key(form: str) -> str:
    return " ".join(_casefold(w) for w in _WORD.findall(_fold_form(form)))


def is_short_word(form: str) -> bool:
    """One word token of fewer than SHORT_WORD_LETTERS letters (`XTB`, `mBank`, `Nova`)."""
    return len(_WORD.findall(form)) == 1 and sum(c.isalpha() for c in form) < SHORT_WORD_LETTERS


def _case_ok(form: str, quote: str) -> bool:
    """A short word matches only capitalized, in lower case where the registry writes it so (`mBank`), or in
    brand casing with an inner capital (`eToro` for KNF's `Etoro`); never as a plain lower-case word."""
    if not is_short_word(form):
        return True
    letters = [c for c in form if c.isalpha()]
    quoted = [c for c in _fold_form(quote) if c.isalpha()]
    if len(letters) <= ACRONYM_LETTERS and all(c.isupper() for c in letters):
        return all(c.isupper() for c in quoted)  # an acronym (`XTB`, `CVI`) only in capitals: "Inc." is no firm
    if not quoted or not quoted[0].islower():
        return True
    return letters[0].islower() or any(c.isupper() for c in quoted[1:])


def owner_by_precedence(firms: list["Firm"]) -> "Firm | None":
    """Of the firms sharing a name form, the only one of the highest type precedence; None on a tie."""
    best = min(TYPE_PRECEDENCE.index(f.type) for f in firms)
    top = [f for f in firms if TYPE_PRECEDENCE.index(f.type) == best]
    return top[0] if len(top) == 1 else None


@dataclass(frozen=True)
class _Form:
    text: str
    pattern: re.Pattern
    tokens: frozenset[str]


@dataclass(frozen=True)
class Firm:
    id: str
    name: str
    type: str
    country: str | None
    aliases: tuple[str, ...]
    domains: tuple[str, ...]
    source_url: str | None

    @property
    def core(self) -> str:
        return core_name(self.name)

    @property
    def name_lines(self) -> tuple[str, ...]:
        return tuple(line.strip() for line in self.name.split(NAME_SEPARATOR) if line.strip())

    @property
    def cores(self) -> tuple[str, ...]:
        """Core of each name line (`mBANK`, `mBank` for the bank and its brokerage unit)."""
        return tuple(dict.fromkeys(c for line in self.name_lines if (c := core_name(line))))


@dataclass(frozen=True)
class FirmMatch:
    firm: Firm
    confidence: float
    method: Literal["name", "domain", "fuzzy", "link"]
    evidence: str | None


class Registry:
    def __init__(self, firms: list[Firm]):
        self.firms = tuple(firms)
        # Demonstration data (the bundled seed) carries no source; the real KNF loader sets `source_url`
        # per firm. Findings say so, so a "not found" never reads as a statement about the KNF register.
        self.demo = not any(f.source_url for f in self.firms)
        self._by_id = {f.id: f for f in firms}
        # A form (other than the firm's own full name) claimed by several firms belongs only to its owner.
        claims: dict[str, list[Firm]] = defaultdict(list)
        for f in firms:
            for form in {_form_key(x) for x in (f.core, *f.name_lines, *f.cores, *f.aliases)} - {_form_key(f.name)}:
                claims[form].append(f)
        owner = {k: (v[0] if len(v) == 1 else owner_by_precedence(v)) for k, v in claims.items()}

        def owned(f: Firm, form: str) -> bool:
            key = _form_key(form)
            return bool(key) and (key == _form_key(f.name) or owner.get(key) is f)

        self._owned = owned
        # Longest form first, so the quote is the fullest form present in the text. `_all_forms` serve
        # `find_name` (R1 on a firm already chosen, e.g. by its domain); `_forms`, the owned ones, decide which
        # firm a text names. A form that folds to no word (zero-width characters only) would match every text.
        self._all_forms: dict[str, list[_Form]] = {
            f.id: [_Form(a, _alias_pattern(a), frozenset(_form_key(a).split()))
                   for a in sorted({f.name, f.core, *f.name_lines, *f.cores, *f.aliases}, key=len, reverse=True)
                   if _form_key(a)]
            for f in firms
        }
        self._forms = {fid: [x for x in forms if owned(self._by_id[fid], x.text)]
                       for fid, forms in self._all_forms.items()}
        # Fuzzy targets: the owned core, tokenized like the text, never a short word.
        self._fuzzy: dict[int, list[tuple[Firm, str]]] = defaultdict(list)
        for f in firms:
            words = [w.lower() for w in _WORD.findall(_fold_form(f.core))]
            if words and owned(f, f.core) and not is_short_word(f.core):
                self._fuzzy[len(words)].append((f, " ".join(words)))

    @classmethod
    def from_csv(cls, path: Path) -> "Registry":
        try:
            with open(path, encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
                if missing:
                    raise RegistryError(f"{path}: missing required column(s) {', '.join(missing)}")
                firms: list[Firm] = []
                seen: set[str] = set()
                for line, row in enumerate(reader, start=2):
                    firm = _parse_row(row, f"{path}:{line}")
                    if firm.id in seen:
                        raise RegistryError(f"{path}:{line}: duplicate id {firm.id}")
                    seen.add(firm.id)
                    firms.append(firm)
        except OSError as exc:
            raise RegistryError(
                f"{path}: cannot read registry ({exc.strerror}); set REGISTRY_CSV to the registry CSV path"
            ) from exc
        except (UnicodeDecodeError, csv.Error) as exc:
            raise RegistryError(f"{path}: not a UTF-8 CSV file ({exc})") from exc
        if not firms:
            raise RegistryError(f"{path}: registry has no firms")
        return cls(firms)

    def get(self, firm_id: str) -> Firm:
        return self._by_id[firm_id]

    def owns(self, firm: Firm, form: str) -> bool:
        """True when `form` identifies `firm` alone: its full name, or a form no firm of higher or equal type
        precedence shares (`XTB` belongs to `XTB S.A.`, not to the Cypriot `XTB Ltd`)."""
        return self._owned(firm, form)

    def find_official_name(self, firm: Firm, text: str) -> str | None:
        """Exact quote of an official form of the firm (its `name`, a name line, or their cores without legal
        forms) in `text`, or None. Aliases (former and trade names, abbreviations) are not official (ZASÓB R1)."""
        official = {_form_key(x) for x in (firm.name, firm.core, *firm.name_lines, *firm.cores)}
        folded, where = fold(text[:SCAN_MAX])
        forms = self._all_forms[firm.id]
        # An official form inside a longer alias mention is no official mention: "Kepler Cheuvreux" (an alias)
        # contains the core "Cheuvreux", "Alfa Inwestycje DM" contains "Alfa Inwestycje".
        alias_spans = [s for f in forms if _form_key(f.text) not in official
                       for s in self._spans(f, text, folded, where)]
        for f in forms:
            if _form_key(f.text) not in official:
                continue
            for s in self._spans(f, text, folded, where):
                if not any(a[0] <= s[0] and s[1] <= a[1] and a != s for a in alias_spans):
                    return text[s[0]:s[1]]
        return None

    def find_name(self, firm: Firm, text: str) -> str | None:
        """Exact quote (from the original text) of the firm's name or an alias in `text`, or None. Searches every
        form of this firm, also one another firm owns: the firm is already chosen (by name or by domain)."""
        span = self._find(text, self._all_forms[firm.id])
        return text[span[0]:span[1]] if span else None

    def _find(self, text: str, forms: list[_Form]) -> tuple[int, int] | None:
        """Span in the ORIGINAL text of the first (longest) form found in the folded text, or None."""
        folded, where = fold(text[:SCAN_MAX])
        for form in forms:
            if span := self._search(form, text, folded, where):
                return span
        return None

    @staticmethod
    def _spans(form: _Form, text: str, folded: str, where: tuple[int, ...]):
        """Every span in the ORIGINAL text where `form` occurs and passes the short-word case guard."""
        for m in form.pattern.finditer(folded):
            span = where[m.start()], where[m.end() - 1] + 1
            if _case_ok(form.text, text[span[0]:span[1]]):
                yield span

    @classmethod
    def _search(cls, form: _Form, text: str, folded: str, where: tuple[int, ...]) -> tuple[int, int] | None:
        return next(cls._spans(form, text, folded, where), None)

    def firm_on_host(self, host: str) -> Firm | None:
        """The firm whose `website_domains` hold `host` (equal or a subdomain), or None."""
        host = _normalize_domain(host)
        if not host:
            return None
        for firm in self.firms:
            if any(host == d or host.endswith("." + d) for d in firm.domains):
                return firm
        return None

    def match_links(self, links) -> FirmMatch | None:
        """Third-party content only: the first link whose host is a firm domain, quoting its href.

        Malformed and non-http(s) hrefs are skipped, never raised.
        """
        for link in links:
            host = http_host(link.href)
            if host and not is_social(host) and (firm := self.firm_on_host(host)) is not None:
                return FirmMatch(firm, LINK_CONFIDENCE, "link", link.href)
        return None

    def match(self, text: str, url: str) -> FirmMatch | None:
        # (rank key, match); the smallest key wins: own domain, confidence, earliest, longest quote.
        candidates: list[tuple[tuple, FirmMatch]] = []
        # Through http_host, like match_links and publisher_firm: a backslash authority
        # ("https://attacker.net\\@firm/", which browsers open as attacker.net) has no domain match (#35 review 2).
        page = http_host(url)
        host = _normalize_domain(page) if page else ""
        social = is_social(host)
        folded, where = fold(text[:SCAN_MAX])
        text_tokens = {_casefold(w) for w in _WORD.findall(folded)}
        fuzzy = self._fuzzy_ratios(folded)
        for firm in self.firms:
            on_domain = not social and any(host == d or host.endswith("." + d) for d in firm.domains)
            # Only forms whose every word occurs in the text can match; this skips nearly every regex.
            forms = [f for f in self._forms[firm.id] if f.tokens and f.tokens <= text_tokens]
            spans = [s for f in forms if (s := self._search(f, text, folded, where))]
            if spans:
                # Rank by the firm's earliest mention in any form; quote its longest form (forms run longest first).
                pos, (start, end) = min(s[0] for s in spans), spans[0]
                match = FirmMatch(firm, NAME_CONFIDENCE, "name", text[start:end])
            elif on_domain:
                match, pos = FirmMatch(firm, DOMAIN_CONFIDENCE, "domain", None), len(text)
            elif (ratio := fuzzy.get(firm.id, 0.0)) >= FUZZY_MIN_RATIO:
                match, pos = FirmMatch(firm, round(ratio / 100 * FUZZY_FACTOR, 3), "fuzzy", None), len(text)
            else:
                continue
            candidates.append(((not on_domain, -match.confidence, pos, -len(match.evidence or "")), match))
        return min(candidates, key=lambda c: c[0])[1] if candidates else None

    def _fuzzy_ratios(self, folded: str) -> dict[str, float]:
        """Best fuzzy ratio (>= FUZZY_MIN_RATIO) of each fuzzy-eligible firm's core against the text's n-grams."""
        # Word runs between punctuation, so a fuzzy n-gram never spans "alfa: inwestycje".
        segments = [ws for seg in _PUNCT.split(folded) if (ws := [w.lower() for w in _WORD.findall(seg)])]
        ratios: dict[str, float] = {}
        for n, targets in self._fuzzy.items():
            grams = list({" ".join(ws[i:i + n]) for ws in segments for i in range(len(ws) - n + 1)})
            if not grams:
                continue
            for firm, target in targets:
                best = process.extractOne(target, grams, scorer=fuzz.ratio, score_cutoff=FUZZY_MIN_RATIO)
                if best:
                    ratios[firm.id] = best[1]
        return ratios


def is_social(host: str) -> bool:
    host = _normalize_domain(host)
    return any(host == s or host.endswith("." + s) for s in SOCIAL_HOSTS)


def http_host(url: str) -> str | None:
    """Host of an absolute http(s) URL, or None for anything else (malformed, other schemes)."""
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not host:
        return None
    # Browsers read "\" as "/", so "https://evil.example\@firm.pl/" opens evil.example while urlsplit
    # reports firm.pl; an authority with a backslash, whitespace or control characters is no host at all.
    if any(c == "\\" or c.isspace() or ord(c) < 0x20 for c in parts.netloc):
        return None
    return host


def _normalize_domain(value: str) -> str:
    """'https://www.Alfa.pl./x' -> 'alfa.pl' (scheme, path, leading www. and trailing dot removed)."""
    value = value.strip()
    host = urlsplit(value if "//" in value else "//" + value).hostname or ""
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _split_list(value: str | None) -> tuple[str, ...]:
    return tuple(v.strip() for v in (value or "").split("|") if v.strip())


def _parse_row(row: dict, where: str) -> Firm:
    firm_id = (row.get("id") or "").strip()
    name = (row.get("name") or "").strip()
    firm_type = (row.get("type") or "").strip()
    if not re.match(UUID_PATTERN, firm_id):
        raise RegistryError(f"{where}: id {firm_id!r} is not a lowercase UUID")
    if not name:
        raise RegistryError(f"{where}: empty name")
    if firm_type not in FIRM_TYPES:
        raise RegistryError(f"{where}: type {firm_type!r} not one of {sorted(FIRM_TYPES)}")
    if not core_name(name):
        raise RegistryError(f"{where}: name {name!r} has nothing left after removing legal forms")
    return Firm(
        id=firm_id,
        name=name,
        type=firm_type,
        country=(row.get("country") or "").strip() or None,
        aliases=_split_list(row.get("aliases")),
        domains=tuple(d for d in map(_normalize_domain, _split_list(row.get("website_domains"))) if d),
        source_url=(row.get("source_url") or "").strip() or None,
    )
