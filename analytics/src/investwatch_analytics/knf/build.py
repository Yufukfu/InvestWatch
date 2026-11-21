"""Build registry rows from fetched KNF records: ids, merges, aliases, domains (design decisions 3-6).

Pure: no I/O. Input is `fetch.fetch_all`'s result, optionally the previous registry (for id carry-over).
"""

from __future__ import annotations

import csv
import re
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from urllib.parse import urlsplit

from ..registry import _normalize_domain, core_name
from . import KnfError
from .fetch import LISTS, SUMMARY_URL, FetchedList
from .parse import COUNTRIES, RawRecord, country_code

#: Fixed namespace of registry ids (ADR 0311). Never change it: every stored `registry_id` derives from it.
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, SUMMARY_URL)
TYPE_ORDER = {s.type: i for i, s in enumerate(LISTS)}
DOMESTIC_TYPES = {"brokerage_house", "brokerage_bank"}
NAME_SEPARATOR = " – "

#: Platform hosts never belong to a firm (same list as analytics-m1-m3's advertiser module).
SOCIAL_HOSTS = (
    "instagram.com", "facebook.com", "fb.com", "tiktok.com", "youtube.com", "youtu.be", "x.com",
    "twitter.com", "t.me", "telegram.me", "linkedin.com", "threads.net",
)

#: Shorter aliases are noise. Short single words (`XTB`, `mBank`) are kept: the registry matches them only
#: as a capitalized word and never fuzzily (design decision 9).
MIN_ALIAS_LETTERS = 3

_QUOTES = str.maketrans("", "", "\"'„”“‚’`«»")
_WORD = re.compile(r"\w+", re.UNICODE)
_COMPANY_SUFFIX = re.compile(
    r"[\s,]+(s\.\s?a\.|sp\.\s?z\s?o\.\s?o\.|spółka akcyjna|ltd\.?|limited|gmbh|ag|a\.s\.|s\.r\.o\.|b\.v\.|n\.v\.|"
    r"sas|s\.a\.s\.|as|asa|a/s|ab|oy|plc|se|s\.p\.a\.|s\.l\.|s\.a\.u\.|o\.c\.p\.|d\.o\.o\.|llc|ood)\s*$",
    re.IGNORECASE,
)
_BRACKETS = re.compile(r"\(([^()]+)\)")
_INFLECTIONS = {
    "dom maklerski": ("domu maklerskiego", "domem maklerskim", "domie maklerskim"),
    "biuro maklerskie": ("biura maklerskiego", "biurem maklerskim", "biurze maklerskim"),
    "departament maklerski": ("departamentu maklerskiego", "departamencie maklerskim"),
}
_TRADE_NAMES = re.compile(r"nazw[ay]\s+handlow[ae]\s*:?\s*(.*)", re.IGNORECASE)
_TRADE_STOP = re.compile(r"(?:https?://|www\.|\[|\(|\bod\s+\d|\bdo\s+\d|\b[\w-]+\.[a-z]{2,24}\b)", re.IGNORECASE)
_HOST_TOKEN = re.compile(
    r"(?<![@\w.-])(?:https?://)?(?:www\.)?((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,24})(?![\w-])(?:/[^\s,;]*)?",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """NFKC, casefold, quotes removed, whitespace collapsed, trailing punctuation stripped."""
    text = unicodedata.normalize("NFKC", name).translate(_QUOTES).casefold()
    return re.sub(r"\s+", " ", text).strip(" ,.;:-–")


def firm_id(name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, normalize_name(name)))


def _stopwords() -> frozenset[str]:
    text = resources.files(__package__).joinpath("stoplist.txt").read_text(encoding="utf-8")
    return frozenset(w for line in text.splitlines() if (w := line.split("#", 1)[0].strip().casefold()))


#: Generic words plus country names (`(Cyprus)` in a firm name is no alias): Polish from the country map.
STOPWORDS = _stopwords() | {w.casefold() for name in COUNTRIES for w in name.split()}
#: Single words that name a well-known company outside the register (`PGE`: PGE Polska Grupa Energetyczna, not
#: PGE Dom Maklerski). Dropped as a bare alias only; longer forms (`PGE Dom Maklerski`) stay.
AMBIGUOUS_WORDS = frozenset({"pge"})


@dataclass
class Firm:
    id: str
    name: str
    type: str
    country: str | None
    source_url: str
    aliases: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    former_names: list[str] = field(default_factory=list)


@dataclass
class BuildReport:
    records: dict[str, int] = field(default_factory=dict)
    merged_same_list: list[str] = field(default_factory=list)
    merged_across_lists: list[str] = field(default_factory=list)
    renamed: list[tuple[str, str]] = field(default_factory=list)  # (former name, current name)
    dropped_aliases: list[tuple[str, str, str]] = field(default_factory=list)  # (firm, alias, reason)
    dropped_domains: list[tuple[str, str]] = field(default_factory=list)  # (domain, reason)
    unknown_countries: list[tuple[str, str]] = field(default_factory=list)  # (firm, country name)
    curated: list[tuple[str, str, bool]] = field(default_factory=list)  # (firm, domain, verified_by_human)


def split_name(record: RawRecord) -> tuple[str, list[str]]:
    """(official name, extra aliases). Bracketed lines (`(ang. Bitstamp Financial Services Ltd.)`) are
    translations, so they are aliases; the other lines (a bank and its brokerage unit) form the name."""
    lines, extra = [], []
    for line in record.name_lines:
        if line.startswith("(") and line.rstrip(" ,.").endswith(")"):
            inner = line[1:line.rindex(")")].strip(" ,")  # "(… S.p.A.,)" -> "… S.p.A."
            extra.append(re.sub(r"^(ang|eng|pol)\.\s*", "", inner, flags=re.IGNORECASE).strip(" ,"))
        else:
            lines.append(line)
    return NAME_SEPARATOR.join(lines), extra


def _without_suffix(text: str) -> str:
    previous = None
    while previous != text:
        previous, text = text, _COMPANY_SUFFIX.sub("", text).strip(" ,")
    return text


def _alias_forms(line: str) -> list[str]:
    """Aliases from one name line: the line, without its company suffix, its core, bracket contents,
    DM forms and the Polish case forms of the legal-form words."""
    outside = re.sub(r"\s+", " ", _BRACKETS.sub(" ", line)).strip()
    forms = [line, outside, _without_suffix(outside), core_name(outside)]
    for inner in _BRACKETS.findall(line):
        forms += [inner, _without_suffix(inner), core_name(inner)]
    lowered = line.casefold()
    core = core_name(outside)
    if "dom maklerski" in lowered and core:
        forms += [f"DM {core}", f"{core} DM"]
    for base, inflected in _INFLECTIONS.items():
        if base in lowered:
            stripped = _without_suffix(line)
            for form in inflected:
                forms.append(re.sub(re.escape(base), form, stripped, flags=re.IGNORECASE))
                if core:
                    forms += [f"{form} {core}", f"{core} {form}"]
    return forms


def trade_names(notes: str) -> list[str]:
    names = []
    for m in _TRADE_NAMES.finditer(notes):
        head = _TRADE_STOP.split(m.group(1), maxsplit=1)[0]
        for part in re.split(r"[,;]", head):
            part = part.strip(" ,;:")
            tokens = part.split()
            # "AccurateFX XGLOBAL AHMZTradeFX": three or more brand-like tokens are separate names.
            if len(tokens) >= 3 and all(_brand_like(t) for t in tokens):
                names += tokens
            elif part:
                names.append(part)
    return names


def _brand_like(token: str) -> bool:
    """A token that reads as a brand on its own: all caps (3+ letters) or capitals after the first letter."""
    letters = [c for c in token if c.isalpha()]
    return len(letters) >= 3 and (token.isupper() or any(c.isupper() for c in token[1:]))


def domains_in(text: str) -> list[str]:
    out = []
    for m in _HOST_TOKEN.finditer(text):
        host = _normalize_domain(m.group(1))
        if host and host not in out:
            out.append(host)
    return out


def _letters(text: str) -> int:
    return sum(c.isalpha() for c in text)


def _alias_rejection(alias: str) -> str | None:
    words = [w.casefold() for w in _WORD.findall(alias)]
    if _letters(alias) < MIN_ALIAS_LETTERS:
        return "too_short"
    if all(w in STOPWORDS for w in words):
        return "generic"
    if len(words) == 1 and words[0] in AMBIGUOUS_WORDS:
        return "ambiguous"
    return None


MANUAL_COLUMNS = ("name", "website_domains", "source_url", "verified_by_human")
#: A registrable host: labels of 1-63 letters, digits or inner hyphens, and a letters-only TLD (so no IP).
_HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}")
#: Suffixes shared by unrelated sites; a firm domain equal to one would claim every page under it.
PUBLIC_SUFFIXES = frozenset({
    "com.pl", "net.pl", "org.pl", "biz.pl", "info.pl", "edu.pl", "gov.pl", "waw.pl", "co.uk", "org.uk",
    "com.cy", "co.com", "com.mt", "co.at", "com.de",
})


@dataclass(frozen=True)
class ManualRow:
    """A curated domain row (`registry/knf_domains_manual.csv`): InvestWatch's attribution aid, not KNF data."""

    name: str
    domains: tuple[str, ...]
    source_url: str
    verified_by_human: bool
    where: str


def load_manual(path: Path) -> list[ManualRow]:
    """Curated domains; a missing file is no rows. Any malformed row fails with `manual_row` naming file:line."""
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in MANUAL_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise KnfError("manual_row", f"{path}: missing column(s) {', '.join(missing)}")
        for line, row in enumerate(reader, start=2):
            rows.append(_manual_row(row, f"{path}:{line}"))
    names: dict[str, str] = {}
    owners: dict[str, ManualRow] = {}
    for r in rows:
        if (first := names.setdefault(normalize_name(r.name), r.where)) != r.where:
            raise KnfError("manual_row", f"{r.where}: {r.name!r} repeats the row at {first}")
        for d in r.domains:
            # One curated domain, or one nested in another, for two firms would silently take one firm's pages.
            for other_domain, other in owners.items():
                if other is not r and (_on(d, [other_domain]) or _on(other_domain, [d])):
                    raise KnfError("manual_row", f"{r.where}: {d} overlaps {other_domain} of {other.name!r} "
                                                 f"at {other.where}")
            owners[d] = r
    return rows


def _manual_row(row: dict, where: str) -> ManualRow:
    def fail(msg: str):
        raise KnfError("manual_row", f"{where}: {msg}")

    name = (row.get("name") or "").strip()
    if not name:
        fail("empty name")
    domains = tuple(_normalize_domain(d) for d in (row.get("website_domains") or "").split("|") if d.strip())
    if not domains:
        fail("no domains")
    for d in domains:
        if not _HOST.fullmatch(d) or d in PUBLIC_SUFFIXES:
            fail(f"{d!r} is not a domain")
        if _on(d, SOCIAL_HOSTS):
            fail(f"{d} is a social platform host")
    source = (row.get("source_url") or "").strip()
    parts = urlsplit(source)
    if "\\" in source or "@" in source:
        fail(f"source_url {source!r} has a backslash or userinfo")
    if parts.scheme != "https":
        fail(f"source_url {source!r} must be an https URL")
    if not _on(_normalize_domain(source), domains):
        fail(f"source_url {source!r} is not on one of {', '.join(domains)}")
    flag = (row.get("verified_by_human") or "").strip().lower()
    if flag not in ("true", "false"):
        fail(f"verified_by_human must be true or false, got {flag!r}")
    return ManualRow(name, domains, source, flag == "true", where)


def build(fetched: dict[str, FetchedList], *, previous: dict[str, str] | None = None,
          manual: list[ManualRow] | None = None) -> tuple[list[Firm], BuildReport]:
    """Registry firms from the fetched lists. `previous` maps a normalized name to its id in the old CSV;
    `manual` adds curated domains by firm name (a row naming no firm fails with `manual_row`)."""
    report = BuildReport()
    previous = previous or {}
    by_name: dict[str, Firm] = {}
    sources: dict[str, set[str]] = defaultdict(set)
    supervisor_hosts: set[str] = set()

    for fl in fetched.values():
        report.records[fl.source.key] = len(fl.records)
        for record in fl.records:
            supervisor_hosts.update(domains_in(record.supervisor))
            name, extra = split_name(record)
            key = normalize_name(name)
            country = "PL" if fl.source.type in DOMESTIC_TYPES else country_code(record.country_name)
            if country is None and fl.source.type not in DOMESTIC_TYPES:
                report.unknown_countries.append((name, record.country_name or ""))
            firm = by_name.get(key)
            if firm is None:
                firm = by_name[key] = Firm(firm_id(name), name, fl.source.type, country, fl.source.url)
            elif fl.source.key in sources[key]:
                report.merged_same_list.append(name)
            else:
                report.merged_across_lists.append(name)
                if TYPE_ORDER[fl.source.type] < TYPE_ORDER[firm.type]:
                    firm.type, firm.country, firm.source_url = fl.source.type, country, fl.source.url
            sources[key].add(fl.source.key)
            firm.former_names += [f for f in record.former_names if f not in firm.former_names]
            lines = [l for l in name.split(NAME_SEPARATOR)]
            candidates = [*(a for line in lines for a in _alias_forms(line)), *extra,
                          *(a for e in extra for a in _alias_forms(e)),
                          *(a for f in record.former_names for a in (f, _without_suffix(f))),
                          *trade_names(record.notes)]
            if len(record.former_names) > 1:
                candidates.append(NAME_SEPARATOR.join(record.former_names))
            for alias in candidates:
                alias = re.sub(r"\s+", " ", alias).strip(" ,;:-–")
                if alias and alias not in firm.aliases:
                    firm.aliases.append(alias)
            firm.domains += [d for d in domains_in(record.notes) if d not in firm.domains]

    for row in manual or []:
        firm = by_name.get(normalize_name(row.name))
        if firm is None:
            raise KnfError("manual_row", f"{row.where}: {row.name!r} is not in the fetched KNF register")
        for d in row.domains:
            if d not in firm.domains:
                firm.domains.append(d)

    firms = list(by_name.values())
    _carry_ids(firms, previous, report)
    _filter_aliases(firms, report)
    _filter_domains(firms, supervisor_hosts, report)
    # Counted after filtering: only curated domains that reach the CSV.
    final = {normalize_name(f.name): f for f in firms}
    for row in manual or []:
        firm = final[normalize_name(row.name)]
        report.curated += [(firm.name, d, row.verified_by_human) for d in row.domains if d in firm.domains]
    firms.sort(key=lambda f: (TYPE_ORDER[f.type], normalize_name(f.name), f.id))
    return firms, report


def _carry_ids(firms: list[Firm], previous: dict[str, str], report: BuildReport) -> None:
    """Keep the previous CSV's id: for the same name first (a firm renamed in an earlier reload keeps the
    carried id, not uuid5 of its new name), else for a struck former name. Never an id another firm holds.
    Firms are visited in a fixed order, so two firms naming the same former name resolve the same way."""
    used = {f.id for f in firms}

    def take(firm: Firm, old_id: str) -> bool:
        if old_id == firm.id or old_id in used:
            return old_id == firm.id
        used.discard(firm.id)
        firm.id = old_id
        used.add(old_id)
        return True

    for firm in sorted(firms, key=lambda f: (TYPE_ORDER[f.type], normalize_name(f.name))):
        if (old_id := previous.get(normalize_name(firm.name))) and take(firm, old_id):
            continue
        for old in [*firm.former_names, NAME_SEPARATOR.join(firm.former_names)]:
            old_id = previous.get(normalize_name(old))
            if old_id and old_id != firm.id and take(firm, old_id):
                report.renamed.append((old, firm.name))
                break


def alias_owner(candidates: list[tuple[str, str]]) -> str | None:
    """Of the (firm id, type) pairs sharing one alias, the firm that keeps it: the only one of the highest
    type precedence (`XTB` stays with the Polish `XTB S.A.`, not the Cypriot `XTB Ltd`); None on a tie."""
    best = min(TYPE_ORDER[t] for _, t in candidates)
    top = {fid for fid, t in candidates if TYPE_ORDER[t] == best}
    return next(iter(top)) if len(top) == 1 else None


def _filter_aliases(firms: list[Firm], report: BuildReport) -> None:
    claims: dict[str, dict[str, str]] = defaultdict(dict)  # alias -> {firm id: type}
    for firm in firms:
        for alias in [firm.name, *firm.aliases]:
            claims[normalize_name(alias)][firm.id] = firm.type
    owners = {k: (next(iter(v)) if len(v) == 1 else alias_owner(list(v.items()))) for k, v in claims.items()}
    for firm in firms:
        own = normalize_name(firm.name)
        kept, seen = [], {own}
        for alias in firm.aliases:
            key = normalize_name(alias)
            if key in seen:
                continue
            seen.add(key)
            reason = _alias_rejection(alias) or ("shared" if owners[key] != firm.id else None)
            if reason:
                report.dropped_aliases.append((firm.name, alias, reason))
            else:
                kept.append(alias)
        firm.aliases = kept


def _on(host: str, bases) -> bool:
    return any(host == b or host.endswith("." + b) for b in bases)


def _filter_domains(firms: list[Firm], supervisor_hosts: set[str], report: BuildReport) -> None:
    """Drop supervisor and social hosts (and their subdomains); a domain several firms list stays with the
    single firm of the highest type precedence, as aliases do (`xtb.com`: Polish XTB S.A. over XTB Ltd)."""
    claims: dict[str, dict[str, str]] = defaultdict(dict)
    for firm in firms:
        for d in firm.domains:
            claims[d][firm.id] = firm.type
    owners = {d: alias_owner(list(v.items())) for d, v in claims.items()}
    for firm in firms:
        kept = []
        for d in firm.domains:
            if _on(d, supervisor_hosts):
                reason = "supervisor"
            elif _on(d, SOCIAL_HOSTS):
                reason = "social"
            elif owners[d] != firm.id:
                reason = "shared"
            else:
                kept.append(d)
                continue
            report.dropped_domains.append((d, reason))
        firm.domains = kept
