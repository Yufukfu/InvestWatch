"""Tiny dependency-free PNG placeholder for screenshot endpoints."""

from __future__ import annotations

import struct
import zlib
from functools import lru_cache

_SIZES = {"desktop": (320, 200), "tablet": (240, 320), "mobile": (180, 360)}


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


@lru_cache(maxsize=None)
def placeholder_png(viewport: str) -> bytes:
    """A flat light-grey RGB image whose size hints at the viewport."""
    width, height = _SIZES.get(viewport, (320, 200))
    row = b"\x00" + b"\xe5\xe7\xeb" * width  # filter byte + pixels
    raw = zlib.compress(row * height, 9)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", raw) + _chunk(b"IEND", b"")
