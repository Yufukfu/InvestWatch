"""Chunking on sentence boundaries (ADR 0310): chunks of at most `chunk_chars`, consecutive chunks overlapping
by `overlap` sentences (R3 `window` + `borderline_margin` = 4), a single longer sentence cut at the limit.

Every chunk is a slice of the original text (`text[start:end]`), so a quote verified against a chunk is also a
verbatim substring of the document.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..preprocessing import Sentence

OVERLAP_SENTENCES = 4


def _next_start(sentences: Sequence[Sentence], i: int, nxt: int, *, chunk_chars: int, overlap: int) -> int:
    """Back up from sentence `nxt` by at most `overlap` sentences, keeping the overlap within half a chunk and
    the next chunk able to hold sentence `nxt`; never back to `i` or earlier (the chunk must add new text)."""
    k = nxt
    while (
        k - 1 > i
        and nxt - (k - 1) <= overlap
        and sentences[nxt - 1].end - sentences[k - 1].start <= chunk_chars // 2
        and sentences[nxt].end - sentences[k - 1].start <= chunk_chars
    ):
        k -= 1
    return k


@dataclass(frozen=True)
class Chunk:
    start: int
    end: int
    text: str


def split_chunks(
    text: str,
    sentences: Sequence[Sentence],
    *,
    chunk_chars: int,
    max_chunks: int,
    overlap: int = OVERLAP_SENTENCES,
) -> tuple[list[Chunk], bool]:
    """(the first `max_chunks` chunks, whether text was left out).

    Every chunk ends later than the previous one. The overlap is up to `overlap` sentences but at most half a
    chunk, so long sentences still advance by about half a chunk per request (group 6 review).
    """
    if chunk_chars < 1:
        raise ValueError("chunk_chars must be at least 1")
    out: list[Chunk] = []
    i, n = 0, len(sentences)
    while i < n and len(out) <= max_chunks:
        s = sentences[i]
        if s.end - s.start > chunk_chars:
            for a in range(s.start, s.end, chunk_chars):
                if len(out) > max_chunks:
                    break
                b = min(a + chunk_chars, s.end)
                out.append(Chunk(a, b, text[a:b]))
            i += 1
            continue
        j = i
        while j + 1 < n and sentences[j + 1].end - s.start <= chunk_chars:
            j += 1
        out.append(Chunk(s.start, sentences[j].end, text[s.start:sentences[j].end]))
        if j == n - 1:
            break
        i = _next_start(sentences, i, j + 1, chunk_chars=chunk_chars, overlap=overlap)
    return out[:max_chunks], len(out) > max_chunks
