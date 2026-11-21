"""Near-duplicate detection and groups in Redis (analytics-embeddings; ADR 0314; plan §2 step 1).

MinHash (`datasketch`) over word 5-shingles of the normalized, lowercased, diacritic-stripped text, and our
own LSH banding in Redis: `bands` buckets of `rows` signature values each. A candidate from any shared bucket
counts only if its Jaccard estimate (share of equal signature values) is at least `threshold`.

A near-duplicate is never dropped: it is analyzed as usual and joins the group of its best match. The group
id is the `document_id` of the group's first member. Keys (all with TTL `NEARDUP_TTL_S`):

- `iw:neardup:v1:b:{band}:{hash}`  set of document ids in one LSH bucket
- `iw:neardup:v1:meta:{id}`        hash: `sig` (base64 uint32) and `url`
- `iw:neardup:v1:doc:{id}`         the document's group id
- `iw:neardup:v1:group:{gid}`      set of member ids

Any Redis error skips detection for that document (`neardup_unavailable`), logged and never raised.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np
from datasketch import MinHash

from .config import NearDupSettings
from .gate import strip_diacritics

log = logging.getLogger(__name__)
PREFIX = "iw:neardup:v1"
SHINGLE_WORDS = 5
#: Verify at most this many candidates (most shared buckets first).
MAX_CANDIDATES = 50
#: Read at most this many ids per bucket (SRANDMEMBER) and stop adding to a bucket that holds this many: a
#: flood of identical spam costs O(1) per copy and its full buckets expire. Any member of a full bucket is a
#: near-copy, so a sample still finds the group.
BUCKET_SAMPLE = 64
MAX_BUCKET_SIZE = 256
MAX_URL_CHARS = 2048
_WORD = re.compile(r"\w+")


def shingles(normalized_text: str, max_chars: int) -> set[str]:
    words = _WORD.findall(strip_diacritics(normalized_text[:max_chars]))
    return {" ".join(words[i:i + SHINGLE_WORDS]) for i in range(len(words) - SHINGLE_WORDS + 1)}


def signature(items: set[str], num_perm: int) -> np.ndarray:
    m = MinHash(num_perm=num_perm, seed=1)
    m.update_batch([s.encode("utf-8", "surrogatepass") for s in sorted(items)])
    return m.hashvalues.astype(np.uint32)


def _encode(sig: np.ndarray) -> str:
    return base64.b64encode(sig.astype("<u4").tobytes()).decode("ascii")


def _decode(raw: Any, num_perm: int) -> np.ndarray | None:
    try:
        data = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError):
        return None
    if len(data) != 4 * num_perm:
        return None
    return np.frombuffer(data, dtype="<u4")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


@dataclass(frozen=True)
class NearDupResult:
    group_id: str
    is_original: bool         # the document is the group's first member
    members: int
    similarity: float | None  # Jaccard estimate to the best match; None when it matched nothing
    original_url: str | None  # the group original's url (None when it is the original itself)


class NearDupIndex:
    def __init__(self, client: Any, settings: NearDupSettings):
        self._r = client
        self._s = settings

    def _bucket_keys(self, sig: np.ndarray) -> list[str]:
        rows = self._s.rows
        le = sig.astype("<u4")  # fixed byte order: the same bucket on every architecture
        return [f"{PREFIX}:b:{b}:{hashlib.sha1(le[b * rows:(b + 1) * rows].tobytes()).hexdigest()[:16]}"
                for b in range(self._s.bands)]

    def observe(self, document_id: str, normalized_text: str, url: str | None) -> NearDupResult | None:
        """Record the document and return its group, or None (too short, or Redis down)."""
        items = shingles(normalized_text, self._s.max_chars)
        if not items:
            return None
        sig = signature(items, self._s.num_perm)
        try:
            return self._observe(document_id, sig, url)
        except Exception as exc:  # noqa: BLE001 - detection is optional, the document is analyzed anyway
            log.warning("near-dup detection skipped", extra={"reason": "neardup_unavailable",
                                                             "document_id": document_id,
                                                             "error": type(exc).__name__})
            return None

    def _observe(self, doc: str, sig: np.ndarray, url: str | None) -> NearDupResult:
        r, ttl = self._r, self._s.ttl_s
        buckets = self._bucket_keys(sig)
        pipe = r.pipeline()
        for key in buckets:
            pipe.srandmember(key, BUCKET_SAMPLE)
            pipe.scard(key)
        replies = pipe.execute()
        shared: Counter[str] = Counter()
        open_buckets = []
        for key, members, size in zip(buckets, replies[0::2], replies[1::2]):
            shared.update(m for m in (_text(x) for x in members or []) if m and m != doc)
            if int(size) < MAX_BUCKET_SIZE:
                open_buckets.append(key)

        best_id, best_sim = None, None
        candidates = sorted(shared, key=lambda c: (-shared[c], c))[:MAX_CANDIDATES]
        if candidates:
            pipe = r.pipeline()
            for c in candidates:
                pipe.hget(f"{PREFIX}:meta:{c}", "sig")
            for c, raw in zip(candidates, pipe.execute()):
                other = _decode(_text(raw), self._s.num_perm) if raw is not None else None
                if other is None:
                    continue
                sim = float(np.mean(other == sig))
                if sim >= self._s.threshold and (best_sim is None or sim > best_sim):
                    best_id, best_sim = c, sim

        existing = _text(r.get(f"{PREFIX}:doc:{doc}"))
        best_gid = (_text(r.get(f"{PREFIX}:doc:{best_id}")) or best_id) if best_id is not None else None
        if existing:  # a redelivery keeps the group it already joined
            gid = existing
            if best_gid != existing:  # its best match now sits in another group: not this group's similarity
                best_sim = None
        else:
            gid = best_gid or doc

        pipe = r.pipeline()
        meta = f"{PREFIX}:meta:{doc}"
        pipe.hset(meta, mapping={"sig": _encode(sig), "url": (url or "")[:MAX_URL_CHARS]})
        pipe.expire(meta, ttl)
        for key in open_buckets:
            pipe.sadd(key, doc)
            pipe.expire(key, ttl)
        pipe.set(f"{PREFIX}:doc:{doc}", gid, ex=ttl)
        group = f"{PREFIX}:group:{gid}"
        pipe.sadd(group, doc)
        pipe.expire(group, ttl)
        if gid != doc:  # the original lives as long as its group
            pipe.expire(f"{PREFIX}:meta:{gid}", ttl)
            pipe.expire(f"{PREFIX}:doc:{gid}", ttl)
        pipe.scard(group)
        pipe.hget(f"{PREFIX}:meta:{gid}", "url")
        out = pipe.execute()
        members, original_url = int(out[-2]), _text(out[-1]) or None
        is_original = gid == doc
        result = NearDupResult(gid, is_original, members, best_sim, None if is_original else original_url)
        if members > 1:
            log.info("neardup", extra={"document_id": doc, "group_id": gid, "similarity": best_sim,
                                       "members": members})
        return result


def build_index(settings: NearDupSettings, redis: Any) -> NearDupIndex | None:
    """`None` without a Redis client (the CLI): near-dup detection is off."""
    if redis is None:
        return None
    return NearDupIndex(redis, settings)
