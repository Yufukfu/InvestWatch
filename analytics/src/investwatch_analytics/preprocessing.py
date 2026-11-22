"""Text preprocessing (`.docs/analytics-plan.md` §2 step 1, rules-only part).

Normalized text feeds the hash and the language guess only. Sentences keep spans into the
ORIGINAL text, so rule evidence is always a verbatim substring of `ScrapedDocument.text`.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

_WS = re.compile(r"\s+")

# A boundary: sentence-final punctuation, then whitespace, then something that starts a sentence.
# Linear on hostile input (scraped text is untrusted): the whitespace run is possessive (`\s++`, never given back)
# and the lookahead allows at most 3 spaces after a footnote marker ("* Ryzyko", "(*) Ryzyko"). The previous
# `\s+(?=...\s*X)` re-scanned the run on every backtrack: ". " + 40 000 spaces took ~15 s (PR #26 review).
_BOUNDARY = re.compile(
    r"(?:(?<=[.!?…])|(?<=[.!?…][”\"»)]))\s++(?=(?:\(\*\)|[\"'„«(\[*¹²³])?\s{0,3}[A-ZĄĆĘŁŃÓŚŹŻ0-9#])|\n\s*\n"
)
# Tokens that end with a period but never end a sentence: legal forms, titles and `<year> r.`
# (usually followed by a capitalized name, so the boundary regex alone would split there).
_ABBREV = re.compile(
    r"(?:\b(?:S\.A|s\.a|sp|Sp|z o\.o|o\.o|np|tj|tzn|tzw|ul|nr|Nr|dr|Dr|prof|Prof|zob|wg|itd|itp|m\.in)|\d\s?r)\.$"
)
# Abbreviations that are also ordinary words ("wszystko jest ok.") end a sentence unless a digit
# follows ("ok. 15%", "tel. 22 …", "art. 44"). `im.`, `ww.`, `lit.` are not listed: before a capital
# they end a sentence ("Zaufaj im."), and before a lowercase word there is no boundary anyway.
_ABBREV_BEFORE_DIGIT = re.compile(r"\b(?:ok|tel|Tel|tys|mln|godz|ust|art|pkt)\.$")
# A digit next, possibly after the opening bracket or quote the boundary allows ("tel. (22) …").
_DIGIT_NEXT = re.compile(r"[(\[\"'„«*]?\s{0,3}\d")
# The abbreviation checks look only at this many characters before a boundary (the longest token is a few
# characters). Searching the whole sentence prefix was quadratic: a skipped boundary keeps `start`, so a chain like
# "S.A. Ab S.A. Ab ..." re-scanned an ever longer prefix (40 000 characters took ~10 s).
_ABBREV_WINDOW = 16

_PL_CHARS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
_PL_WORDS = {
    "i", "w", "z", "na", "do", "nie", "się", "jest", "to", "że", "od", "za", "po", "dla", "oraz",
    "lub", "czy", "jak", "twoje", "twój", "konto", "inwestuj", "zysk", "ryzyko", "rocznie", "nasi",
}
_EN_WORDS = {
    "the", "and", "of", "to", "a", "in", "is", "are", "with", "for", "on", "your", "you", "risk",
    "money", "come", "losing", "high", "complex", "this", "that", "be", "or", "an",
}


def normalize(text: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFKC", text)).strip()


def content_hash(text: str) -> str:
    return _hash_of_normalized(normalize(text))


def _hash_of_normalized(norm: str) -> str:
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def guess_language(text: str) -> str | None:
    """`pl` or `en` by Polish diacritics and stopwords; None for empty text."""
    return _language_of_normalized(normalize(text))


def _language_of_normalized(norm: str) -> str | None:
    norm = norm.lower()
    if not norm:
        return None
    words = re.findall(r"[a-ząćęłńóśźż]+", norm)
    pl = sum(w in _PL_WORDS for w in words) + 2 * sum(c in _PL_CHARS for c in norm)
    en = sum(w in _EN_WORDS for w in words)
    return "pl" if pl >= en else "en"


@dataclass(frozen=True)
class Sentence:
    text: str
    start: int
    end: int


def split_sentences(text: str) -> list[Sentence]:
    sentences: list[Sentence] = []
    start = 0
    for m in _BOUNDARY.finditer(text):
        paragraph_break = "\n\n" in re.sub(r"[^\n]", "", m.group(0))
        tail = max(start, m.start() - _ABBREV_WINDOW)  # `\b` still sees the character before `tail`
        digit_next = _DIGIT_NEXT.match(text, m.end()) is not None
        if not paragraph_break and (
            _ABBREV.search(text, tail, m.start())
            or (digit_next and _ABBREV_BEFORE_DIGIT.search(text, tail, m.start()))
        ):
            continue
        _append(sentences, text, start, m.start())
        start = m.end()
    _append(sentences, text, start, len(text))
    return sentences


def _append(out: list[Sentence], text: str, start: int, end: int) -> None:
    chunk = text[start:end]
    stripped = chunk.strip()
    if not stripped:
        return
    lead = len(chunk) - len(chunk.lstrip())
    s = start + lead
    out.append(Sentence(stripped, s, s + len(stripped)))


@dataclass(frozen=True)
class Preprocessed:
    original: str
    normalized: str
    content_hash: str
    lang: str | None
    sentences: list[Sentence] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.normalized


def preprocess(text: str) -> Preprocessed:
    # NFKC once: hash and language derive from the same normalized text (three passes took ~26 s on 2 MB of 'ﬁ').
    norm = normalize(text)
    return Preprocessed(
        original=text,
        normalized=norm,
        content_hash=_hash_of_normalized(norm),
        lang=_language_of_normalized(norm),
        sentences=split_sentences(text),
    )
