"""Embedding rescue in the topic gate (change analytics-embedding-gate; ADR 0314 amendment).

The dictionary decides first (`gate.evaluate`). Only a gated document it drops, with at least
`GATE_EMBED_MIN_CHARS` characters, is embedded and compared with class centroids built from the seed lines of
`gate_terms.yaml`: `margin = max cos(on-topic class) - cos(off_topic)`. The document passes when
`margin >= GATE_EMBED_MIN_MARGIN`. Embeddings can only rescue, never drop what the dictionary passed.

Centroids are built by `warm()`, which the worker and the CLI call outside any message, so a document never costs
more than its own one embedding call. Without centroids or a vector the gate stays dictionary-only
(`dictionary_only_fallback`); the reason is logged once per change, never per document. Nothing here raises.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from .config import GateSettings
from .gate import OFF_TOPIC_CLASS, GateDecision

if TYPE_CHECKING:
    from .embeddings import Embedder, EmbedOutcome

log = logging.getLogger(__name__)
OFF_TOPIC = OFF_TOPIC_CLASS
EMBEDDING = "embedding"
FALLBACK = "dictionary_only_fallback"
_NOT_BUILT = "no_centroids"


def seed_hash(seed: str) -> str:
    """Cache key of a seed line in `iw:emb:v1:*`; prefixed so it never equals a document's content hash."""
    return hashlib.sha256(f"iw-gate-seed\0{seed}".encode()).hexdigest()


@dataclass(frozen=True)
class Rescue:
    path: str  # embedding | dictionary_only_fallback
    passed: bool
    similarity: float | None = None
    margin: float | None = None
    outcome: "EmbedOutcome | None" = None


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


class GateEmbedding:
    def __init__(self, embedder: "Embedder", seeds: dict[str, list[str]], settings: GateSettings, *,
                 retry_s: float, clock: Callable[[], float] = time.monotonic):
        self._embedder = embedder
        self._seeds = seeds
        self._s = settings
        self._retry_s = retry_s
        self._clock = clock
        self._last_attempt: float | None = None
        self._state: str | None = _NOT_BUILT  # None = working; otherwise the last logged reason
        self.centroids: dict[str, np.ndarray] = {}

    @property
    def ready(self) -> bool:
        return bool(self.centroids)

    def warm(self) -> bool:
        """Build the centroids if missing; at most one attempt per `retry_s`. True when they exist."""
        if self.ready:
            return True
        now = self._clock()
        if self._last_attempt is not None and now - self._last_attempt < self._retry_s:
            return False
        self._last_attempt = now
        built: dict[str, np.ndarray] = {}
        for name, seeds in self._seeds.items():
            vectors = []
            for seed in seeds:
                outcome = self._embed(seed, seed_hash(seed))
                if outcome.vector is None:
                    self._degraded(outcome.status)
                    return False
                vectors.append(np.asarray(outcome.vector, dtype=np.float32))
            built[name] = _unit(np.mean(vectors, axis=0))
        self.centroids = built
        self._restored()
        return True

    def rescue(self, text: str, content_hash: str | None) -> Rescue:
        if not self.ready:
            return Rescue(FALLBACK, False)  # warm() already logged why the centroids are missing
        outcome = self._embed(text, content_hash)
        if outcome.vector is None:
            self._degraded(outcome.status)
            return Rescue(FALLBACK, False, outcome=outcome)
        v = _unit(np.asarray(outcome.vector, dtype=np.float32))
        on = max(float(v @ c) for name, c in self.centroids.items() if name != OFF_TOPIC)
        # Decide on the same 3-place figure that is logged and that eval/gate_calibrate.py sweeps, so a drop never
        # shows a margin equal to the threshold (seen in the manual run: logged 0.03, compared as 0.0298).
        margin = round(on - float(v @ self.centroids[OFF_TOPIC]), 3)
        self._restored()
        return Rescue(EMBEDDING, margin >= self._s.embed_min_margin, round(on, 3), margin, outcome)

    def _embed(self, text: str, content_hash: str | None) -> "EmbedOutcome":
        try:
            return self._embedder.embed(text, content_hash)
        except Exception as exc:  # noqa: BLE001 - the embedder never raises; a test double might
            from .embeddings import EmbedOutcome
            log.warning("embed call failed", extra={"reason": "embed_unavailable", "error": type(exc).__name__})
            return EmbedOutcome(None, None, "embed_unavailable")

    def _degraded(self, reason: str) -> None:
        if reason != self._state:
            log.warning("embedding gate degraded", extra={"reason": reason, "gate_path": FALLBACK})
            self._state = reason

    def _restored(self) -> None:
        if self._state is not None:
            msg = "embedding gate ready" if self._state == _NOT_BUILT else "embedding gate restored"
            log.info(msg, extra={"reason": "embedding_gate_ready", "previous": self._state,
                                 "classes": len(self.centroids)})
            self._state = None


def decide(decision: GateDecision, text: str, content_hash: str | None, gate_embedding: GateEmbedding | None,
           settings: GateSettings) -> tuple[GateDecision, "EmbedOutcome | None"]:
    """The dictionary decision, possibly rescued. Returns the decision and the document's `EmbedOutcome` (None when
    the gate did not embed), so the pipeline reuses the vector for `model.embedder` instead of embedding again."""
    if decision.reason != "off_topic":
        return decision, None  # passed on the dictionary, bypassed or disabled: embeddings never re-judge
    if len(text) < settings.embed_min_chars:
        return decision, None  # too short to embed: the dictionary decides (path stays `dictionary`)
    if gate_embedding is None:
        return dataclasses.replace(decision, path=FALLBACK), None
    r = gate_embedding.rescue(text, content_hash)
    model = r.outcome.model if r.outcome is not None else None
    return dataclasses.replace(decision, passed=r.passed, reason=EMBEDDING if r.passed else "off_topic",
                               path=r.path, similarity=r.similarity, margin=r.margin,
                               embedder=model or decision.embedder), r.outcome
