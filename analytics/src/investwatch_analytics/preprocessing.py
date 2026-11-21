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
_BOUNDARY = re.compile(
    r"(?:(?<=[.!?…])|(?<=[.!?…][”\"»)]))\s+(?=[\"'„«(\[*¹²³]?[A-ZĄĆĘŁŃÓŚŹŻ0-9#])|\n\s*\n"
)
# Tokens that end with a period but do not end a sentence.
_ABBREV = re.compile(
    r"(?:\b(?:S\.A|s\.a|sp|Sp|z o\.o|o\.o|np|tj|tzn|tzw|ok|ul|nr|Nr|dr|Dr|prof|Prof|tel|Tel|zob|wg|tys|mln|itd|itp|m\.in|godz|ust|lit|art|pkt|ww|im)\.)$"
)

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
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def guess_language(text: str) -> str | None:
    """`pl` or `en` by Polish diacritics and stopwords; None for empty text."""
    norm = normalize(text).lower()
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
        if not paragraph_break and _ABBREV.search(text[start:m.start()]):
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
    norm = normalize(text)
    return Preprocessed(
        original=text,
        normalized=norm,
        content_hash=content_hash(text),
        lang=guess_language(text),
        sentences=split_sentences(text),
    )
