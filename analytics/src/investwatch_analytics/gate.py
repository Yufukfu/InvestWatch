"""Investment topic gate, dictionary part (analytics-embeddings; ADR 0314; plan §2 step 2). Pure: no I/O.

`evaluate()` decides from the normalized text, the source kind and the registry match. A document is dropped
only when it has no dictionary hit (recall first); `firm_own` bypasses the gate, because M2 must check every
page a firm publishes itself. The caller logs a drop with `GateDecision.log_extra()` (figures only, no text).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import GateSettings

DEFAULT_TERMS = Path(__file__).with_name("gate_terms.yaml")
#: Only the start of a document is scanned: the topic shows in the headline and lead, and the cap bounds the
#: regex cost on hostile 2 MB input (measured ~0.6 s worst case at this size).
MAX_GATE_CHARS = 200_000
_KEYS = {"version", "terms", "prefixes", "centroids"}
_POLISH_EXTRA = str.maketrans({"ł": "l", "Ł": "l"})  # NFD does not decompose ł


class GateTermsError(ValueError):
    """`gate_terms.yaml` is invalid; the message names the file and the key."""


def strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.translate(_POLISH_EXTRA).lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@dataclass(frozen=True)
class GateTerms:
    pattern: re.Pattern[str]
    centroids: dict[str, list[str]] = field(default_factory=dict)


def _word(word: str, prefixes: str) -> str:
    if word.endswith("*"):
        stem = re.escape(word[:-1])
        return rf"(?:{prefixes}){stem}\w*" if prefixes else rf"{stem}\w*"
    return re.escape(word)


def _compile(terms: list[str], prefixes: list[str]) -> re.Pattern[str]:
    pre = "|".join(re.escape(p) for p in prefixes)
    pre = f"(?:{pre})?" if pre else ""
    alternatives = []
    for term in terms:
        words = strip_diacritics(term).split()
        alternatives.append(r"\s+".join(_word(w, pre) for w in words))
    # Boundaries: a term never matches inside another word (`ETF` in `netflix`, `forex` in `forexpo`).
    # The first-character lookahead lets the engine skip positions no term can start at (digits, dots).
    firsts = sorted({a[0] for a in (strip_diacritics(t) for t in terms + prefixes) if a})
    first_class = "[" + "".join(re.escape(c) for c in firsts) + "]"
    return re.compile(r"(?<!\w)(?=" + first_class + r")(?:" + "|".join(alternatives) + r")(?!\w)")


def _fail(path: Path, key: str, why: str) -> GateTermsError:
    return GateTermsError(f"{path.name}: `{key}` {why}")


def load_terms(path: str | Path | None = None) -> GateTerms:
    p = Path(path) if path else DEFAULT_TERMS
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise _fail(p, "version", "must be 1")
    unknown = sorted(set(data) - _KEYS)
    if unknown:
        raise _fail(p, unknown[0], "is not a known key (version, terms, prefixes, centroids)")
    terms = data.get("terms")
    if not isinstance(terms, list) or not terms:
        raise _fail(p, "terms", "must be a non-empty list")
    for t in terms:
        if not isinstance(t, str) or not t.strip() or any(w.strip("*") == "" for w in t.split()):
            raise _fail(p, "terms", f"has an empty, non-string or bare `*` entry: {t!r}")
    prefixes = data.get("prefixes") or []
    if not isinstance(prefixes, list) or not all(isinstance(x, str) and x.strip() for x in prefixes):
        raise _fail(p, "prefixes", "must be a list of non-empty strings")
    centroids = data.get("centroids") or {}
    if not isinstance(centroids, dict):
        raise _fail(p, "centroids", "must be a mapping of class -> seed phrases")
    for name, seeds in centroids.items():
        if not isinstance(seeds, list) or not seeds or not all(isinstance(s, str) and s.strip() for s in seeds):
            raise _fail(p, f"centroids.{name}", "must be a non-empty list of seed phrases")
    return GateTerms(pattern=_compile([t.strip() for t in terms], [strip_diacritics(x.strip()) for x in prefixes]),
                     centroids={str(k): list(v) for k, v in centroids.items()})


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    reason: str  # dictionary | off_topic | bypassed_firm_own | gate_disabled
    dict_hits: int
    similarity: float | None = None  # set only by the (stretch) similarity rescue
    embedder: str | None = None

    def log_extra(self) -> dict[str, Any]:
        return {"reason": self.reason, "dict_hits": self.dict_hits, "similarity": self.similarity,
                "embedder": self.embedder}


def evaluate(normalized_text: str, *, source_kind: str, firm_matched: bool, terms: GateTerms,
             settings: GateSettings, embedder: str | None = None) -> GateDecision:
    if not settings.enabled:
        return GateDecision(True, "gate_disabled", 0, embedder=embedder)
    if source_kind == "firm_own":
        return GateDecision(True, "bypassed_firm_own", 0, embedder=embedder)
    text = strip_diacritics(normalized_text[:MAX_GATE_CHARS])
    hits = sum(1 for _ in terms.pattern.finditer(text)) + int(firm_matched)
    return GateDecision(hits > 0, "dictionary" if hits else "off_topic", hits, embedder=embedder)
