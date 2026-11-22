"""The renderer's limits, from the environment (config is env-only). A bad value stops the process at start."""

import os
from dataclasses import dataclass

DEFAULT_TIMEOUT_SECONDS = 90.0
DEFAULT_MAX_PAGE_HEIGHT = 12000  # CSS pixels
DEFAULT_MAX_PNG_BYTES = 8_000_000
DEFAULT_CONCURRENCY = 1
DEFAULT_MAX_BLOCKS = 600  # blocks per viewport


def _positive(name: str, default: float, kind: type) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = kind(raw)
    except ValueError:
        raise ValueError(f"{name} must be a positive number, got {raw!r}") from None
    if value <= 0:
        raise ValueError(f"{name} must be a positive number, got {raw!r}")
    return value


@dataclass(frozen=True)
class RenderLimits:
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_page_height: int = DEFAULT_MAX_PAGE_HEIGHT
    max_png_bytes: int = DEFAULT_MAX_PNG_BYTES
    concurrency: int = DEFAULT_CONCURRENCY
    max_blocks: int = DEFAULT_MAX_BLOCKS

    @classmethod
    def from_env(cls) -> "RenderLimits":
        return cls(
            timeout_seconds=_positive("RENDER_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, float),
            max_page_height=int(_positive("RENDER_MAX_PAGE_HEIGHT", DEFAULT_MAX_PAGE_HEIGHT, int)),
            max_png_bytes=int(_positive("RENDER_MAX_PNG_BYTES", DEFAULT_MAX_PNG_BYTES, int)),
            concurrency=int(_positive("RENDER_CONCURRENCY", DEFAULT_CONCURRENCY, int)),
            max_blocks=int(_positive("RENDER_MAX_BLOCKS", DEFAULT_MAX_BLOCKS, int)),
        )
