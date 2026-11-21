"""Parse one KNF list page into raw records (`openspec/changes/archive/2026-11-21-analytics-knf-registry/evidence.md`, Format).

Records are the `<table>`s inside `<div id="entityTable">`; fields are read by their `th` label text, never by
CSS class. A cell is a list of lines (split at `<br>`, `<li>`, `<p>`), each line a list of (text, struck) runs,
because a `<strike>` may span several lines or only one letter of a line (the PEKAO artifact).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from . import KnfError

NAME_LABELS = ("Nazwa", "Nazwa podmiotu")
COUNTRY_LABEL = "Państwo macierzyste"
SUPERVISOR_LABEL = "Organ nadzoru"
NOTES_LABEL = "Dodatkowe informacje"

#: `Państwo macierzyste` (Polish) -> ISO 3166-1 alpha-2. Every value seen on the foreign lists on 2026-11-21,
#: plus the remaining EU/EEA states.
COUNTRIES = {
    "Austria": "AT", "Belgia": "BE", "Bułgaria": "BG", "Chorwacja": "HR", "Cypr": "CY", "Czechy": "CZ",
    "Dania": "DK", "Estonia": "EE", "Finlandia": "FI", "Francja": "FR", "Gibraltar": "GI", "Grecja": "GR",
    "Hiszpania": "ES", "Holandia": "NL", "Niderlandy": "NL", "Irlandia": "IE", "Islandia": "IS",
    "Liechtenstein": "LI", "Litwa": "LT", "Luksemburg": "LU", "Łotwa": "LV", "Malta": "MT", "Niemcy": "DE",
    "Norwegia": "NO", "Polska": "PL", "Portugalia": "PT", "Rumunia": "RO", "Słowacja": "SK", "Słowenia": "SI",
    "Szwecja": "SE", "Węgry": "HU", "Włochy": "IT",
}

_LINE_BREAK_TAGS = {"br", "li", "p", "div"}
_WS = re.compile(r"\s+")

Line = list[tuple[str, bool]]


def _clean(text: str) -> str:
    return _WS.sub(" ", text.replace("\xa0", " ")).strip()


def line_text(line: Line, *, include_struck: bool = True) -> str:
    return _clean("".join(t for t, struck in line if include_struck or not struck))


def _wholly_struck(line: Line) -> bool:
    return bool(line_text(line)) and not line_text(line, include_struck=False)


@dataclass
class RawRecord:
    """One firm's table, as published. `cells` maps a `th` label to its lines."""

    cells: dict[str, list[Line]]
    page: int = 1

    @property
    def fingerprint(self) -> str:
        """The record's full visible text, used to tell a new record from a repeated page."""
        return "\x1f".join(f"{k}={'|'.join(line_text(l) for l in v)}" for k, v in sorted(self.cells.items()))

    def _cell(self, label: str) -> list[Line]:
        return self.cells.get(label, [])

    def _name_cell(self) -> list[Line]:
        for label in NAME_LABELS:
            if label in self.cells:
                return self.cells[label]
        return []

    @property
    def name_lines(self) -> tuple[str, ...]:
        """Current name lines: every line that is not wholly struck through, struck letters kept."""
        return tuple(t for line in self._name_cell() if not _wholly_struck(line) and (t := line_text(line)))

    @property
    def former_names(self) -> tuple[str, ...]:
        return tuple(line_text(line) for line in self._name_cell() if _wholly_struck(line))

    @property
    def country_name(self) -> str | None:
        return " ".join(line_text(l, include_struck=False) for l in self._cell(COUNTRY_LABEL)).strip() or None

    @property
    def supervisor(self) -> str:
        return " ".join(line_text(l) for l in self._cell(SUPERVISOR_LABEL))

    @property
    def notes(self) -> str:
        """`Dodatkowe informacje` without struck-through parts (former trade names and domains)."""
        return " ".join(line_text(l, include_struck=False) for l in self._cell(NOTES_LABEL)).strip()


@dataclass
class _State:
    records: list[RawRecord] = field(default_factory=list)
    found_container: bool = False


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.state = _State()
        self._div_depth = 0  # >0 while inside #entityTable
        self._table: dict[str, list[Line]] | None = None
        self._in = None  # "th" | "td" | None
        self._label: list[str] = []
        self._lines: list[Line] = [[]]
        self._strike = 0

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            if self._div_depth:
                self._div_depth += 1
            elif dict(attrs).get("id") == "entityTable":
                self._div_depth = 1
                self.state.found_container = True
            if self._in == "td":
                self._lines.append([])
            return
        if not self._div_depth:
            return
        if tag == "table":
            self._table = {}
        elif tag == "th" and self._table is not None:
            self._in, self._label = "th", []
        elif tag == "td" and self._table is not None:
            self._in, self._lines = "td", [[]]
        elif tag == "strike":
            self._strike += 1
        elif tag in _LINE_BREAK_TAGS and self._in == "td":
            self._lines.append([])

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self._div_depth and self._in == "td":
            self._lines.append([])

    def handle_endtag(self, tag):
        if tag == "div" and self._div_depth:
            self._div_depth -= 1
            return
        # Outside the container nothing was opened (handle_starttag returns early), so no guard is needed here.
        if tag == "strike":
            self._strike = max(0, self._strike - 1)
        elif tag == "th" and self._in == "th":
            self._in = None
        elif tag == "td" and self._in == "td":
            label = _clean("".join(self._label))
            if self._table is not None and label:
                self._table[label] = [l for l in self._lines if line_text(l)]
            self._in = None
        elif tag in ("li", "p") and self._in == "td":
            self._lines.append([])
        elif tag == "table" and self._table is not None:
            self.state.records.append(RawRecord(self._table))
            self._table = None

    def handle_data(self, data):
        if self._in == "th":
            self._label.append(data)
        elif self._in == "td":
            self._lines[-1].append((data, self._strike > 0))


def parse_page(html: str, *, where: str, page: int = 1) -> list[RawRecord]:
    """Records of one list page. Raises `layout_changed` when the container or the name label is missing."""
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    if not parser.state.found_container:
        raise KnfError("layout_changed", f"{where} page {page}: no #entityTable")
    records = parser.state.records
    for r in records:
        r.page = page
    if records and not any(label in r.cells for r in records for label in NAME_LABELS):
        raise KnfError("layout_changed", f"{where} page {page}: no {' / '.join(NAME_LABELS)} label")
    return records


def country_code(name: str | None) -> str | None:
    return COUNTRIES.get(name) if name else None
