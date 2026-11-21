"""Loader of the real KNF register of investment firms (change `analytics-knf-registry`, ADR 0311).

Run by hand: `python -m investwatch_analytics.knf --out registry/knf.csv`. Never imported by the worker.
"""

from __future__ import annotations


class KnfError(RuntimeError):
    """A failed load. `reason` is one of the codes in the `knf-registry-loader` spec (fetch_failed,
    list_moved, layout_changed, count_dropped, invalid_output, manual_row)."""

    def __init__(self, reason: str, message: str):
        super().__init__(f"{reason}: {message}")
        self.reason = reason
        self.message = message
