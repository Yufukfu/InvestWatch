"""KNF firm registry: CSV loader and document-to-firm matching (`.docs/analytics-plan.md` §2 step 3, §3).

Per firm, the strongest signal: name or alias in the text (0.95), page host equal to or a
subdomain of a firm domain (0.9), fuzzy match of the name core on word n-grams (ratio x 0.85,
only at ratio >= 88, which for short names means an exact word anyway).
Across firms: the firm whose domain hosts the page wins (a firm's own page that names a partner
firm is still that firm's page), then the highest confidence, then the earliest and the longest quote.
Name matches quote the ORIGINAL text, so the quote can serve as rule evidence.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from rapidfuzz import fuzz

from .models import UUID_PATTERN

FIRM_TYPES = {"brokerage_house", "brokerage_bank", "foreign_branch", "foreign_no_branch"}
REQUIRED_COLUMNS = ("id", "name", "type")

NAME_CONFIDENCE = 0.95
DOMAIN_CONFIDENCE = 0.9
LINK_CONFIDENCE = 0.9  # a link to a firm domain in third-party content (change analytics-m1-m3)
FUZZY_FACTOR = 0.85
FUZZY_MIN_RATIO = 88

_LEGAL_FORMS = re.compile(
    r"\(oddział w polsce\)|biuro maklerskie|dom maklerski|\bs\.\s?a\.|\bsp\.\s?z\s?o\.\s?o\.|\bltd\b\.?|\bdm\b",
    re.IGNORECASE,
)
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
    """Firm name without legal-form words, e.g. 'Alfa Inwestycje Dom Maklerski S.A.' -> 'Alfa Inwestycje'."""
    stripped = _LEGAL_FORMS.sub(" ", name)
    return re.sub(r"\s+", " ", stripped).strip(" -–,.")


def _alias_pattern(alias: str) -> re.Pattern:
    body = r"\s+".join(re.escape(t) for t in alias.split())
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


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
        # Longest alias first, so the quote is the fullest form present in the text.
        self._patterns = {
            f.id: [_alias_pattern(a) for a in sorted({f.name, f.core, *f.aliases}, key=len, reverse=True) if a]
            for f in firms
        }

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

    def find_name(self, firm: Firm, text: str) -> str | None:
        """Exact quote of the firm's name or an alias in `text`, or None."""
        m = self._find(firm, text)
        return m.group(0) if m else None

    def _find(self, firm: Firm, text: str) -> re.Match | None:
        for pattern in self._patterns[firm.id]:
            m = pattern.search(text)
            if m:
                return m
        return None

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
        # Word runs between punctuation, so a fuzzy n-gram never spans "alfa: inwestycje".
        segments = [words for seg in _PUNCT.split(text) if (words := [w.lower() for w in _WORD.findall(seg)])]
        for firm in self.firms:
            on_domain = not is_social(host) and any(host == d or host.endswith("." + d) for d in firm.domains)
            if m := self._find(firm, text):
                # Rank by the firm's earliest mention in any form; quote its longest form.
                pos = min(h.start() for p in self._patterns[firm.id] if (h := p.search(text)))
                match = FirmMatch(firm, NAME_CONFIDENCE, "name", m.group(0))
            elif on_domain:
                match, pos = FirmMatch(firm, DOMAIN_CONFIDENCE, "domain", None), len(text)
            elif (ratio := _best_fuzzy_in(firm.core, segments)) >= FUZZY_MIN_RATIO:
                match, pos = FirmMatch(firm, round(ratio / 100 * FUZZY_FACTOR, 3), "fuzzy", None), len(text)
            else:
                continue
            candidates.append(((not on_domain, -match.confidence, pos, -len(match.evidence or "")), match))
        return min(candidates, key=lambda c: c[0])[1] if candidates else None


def _best_fuzzy_in(core: str, segments: list[list[str]]) -> float:
    """Best ratio over all segments; the core name is tokenized once, and segments shorter than it are skipped."""
    # Tokenize the name like the text, so "Alfa-Beta Inwestycje" compares as "alfa beta inwestycje".
    target_words = [w.lower() for w in _WORD.findall(core)]
    if not target_words:  # a name of punctuation only ("&") would otherwise match every text at ratio 100
        return 0.0
    n, target = len(target_words), " ".join(target_words)
    best = 0.0
    for words in segments:
        for i in range(len(words) - n + 1):
            best = max(best, fuzz.ratio(target, " ".join(words[i:i + n])))
    return best


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
