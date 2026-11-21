"""KNF firm registry: CSV loader and document-to-firm matching (`.docs/analytics-plan.md` §2 step 3, §3).

Matching order (best confidence wins): name or alias in the text (0.95), page host equal to or a
subdomain of a firm domain (0.9), fuzzy match of the name core on word n-grams (ratio x 0.85,
only at ratio >= 88, which for short names means an exact word anyway).
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
FUZZY_FACTOR = 0.85
FUZZY_MIN_RATIO = 88

_LEGAL_FORMS = re.compile(
    r"\(oddział w polsce\)|biuro maklerskie|dom maklerski|\bs\.\s?a\.|\bsp\.\s?z\s?o\.\s?o\.|\bltd\b\.?|\bdm\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"\w+", re.UNICODE)


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
    method: Literal["name", "domain", "fuzzy"]
    evidence: str | None


class Registry:
    def __init__(self, firms: list[Firm]):
        self.firms = tuple(firms)
        self._by_id = {f.id: f for f in firms}
        # Longest alias first, so the quote is the fullest form present in the text.
        self._patterns = {
            f.id: [_alias_pattern(a) for a in sorted({f.name, f.core, *f.aliases}, key=len, reverse=True) if a]
            for f in firms
        }

    @classmethod
    def from_csv(cls, path: Path) -> "Registry":
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
                if missing:
                    raise RegistryError(f"{path}: missing required column(s) {', '.join(missing)}")
                firms = [_parse_row(row, f"{path}:{line}") for line, row in enumerate(reader, start=2)]
        except OSError as exc:
            raise RegistryError(f"{path}: cannot read registry ({exc.strerror})") from exc
        if not firms:
            raise RegistryError(f"{path}: registry has no firms")
        return cls(firms)

    def get(self, firm_id: str) -> Firm:
        return self._by_id[firm_id]

    def find_name(self, firm: Firm, text: str) -> str | None:
        """Exact quote of the firm's name or an alias in `text`, or None."""
        for pattern in self._patterns[firm.id]:
            m = pattern.search(text)
            if m:
                return m.group(0)
        return None

    def match(self, text: str, url: str) -> FirmMatch | None:
        candidates: list[FirmMatch] = []
        host = (urlsplit(url).hostname or "").lower()
        words = [w.lower() for w in _WORD.findall(text)]
        for firm in self.firms:
            quote = self.find_name(firm, text)
            if quote:
                candidates.append(FirmMatch(firm, NAME_CONFIDENCE, "name", quote))
            elif any(host == d or host.endswith("." + d) for d in firm.domains):
                candidates.append(FirmMatch(firm, DOMAIN_CONFIDENCE, "domain", None))
            elif (ratio := _best_fuzzy(firm.core, words)) >= FUZZY_MIN_RATIO:
                candidates.append(FirmMatch(firm, round(ratio / 100 * FUZZY_FACTOR, 3), "fuzzy", None))
        return max(candidates, key=lambda m: m.confidence, default=None)


def _best_fuzzy(core: str, words: list[str]) -> float:
    n = len(core.split())
    target = core.lower()
    grams = (" ".join(words[i:i + n]) for i in range(len(words) - n + 1))
    return max((fuzz.ratio(target, g) for g in grams), default=0.0)


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
    return Firm(
        id=firm_id,
        name=name,
        type=firm_type,
        country=(row.get("country") or "").strip() or None,
        aliases=_split_list(row.get("aliases")),
        domains=tuple(d.lower() for d in _split_list(row.get("website_domains"))),
        source_url=(row.get("source_url") or "").strip() or None,
    )
