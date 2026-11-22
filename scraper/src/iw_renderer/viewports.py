"""The three viewports of the contract's `screenshots` and `block.viewport` enum (design decision 9)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Viewport:
    name: str
    width: int
    height: int
    is_mobile: bool  # makes the browser honour `<meta name="viewport">`, which resizing one page never does
    has_touch: bool


VIEWPORTS = {
    viewport.name: viewport
    for viewport in (
        Viewport("desktop", 1440, 900, is_mobile=False, has_touch=False),
        Viewport("tablet", 820, 1180, is_mobile=False, has_touch=True),
        Viewport("mobile", 390, 844, is_mobile=True, has_touch=True),
    )
}
