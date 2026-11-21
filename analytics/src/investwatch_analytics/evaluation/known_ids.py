"""Rule and signal ids the gold set may label, per module.

The static lists are copied from the stage-2 catalogues (`m2_rules.yaml` on `analytics-llm-p0`,
`m1_signals.yaml` / `m3_signals.yaml` on `analytics-m1-m3`), so the gold set can label every module before
those changes are merged into this build. Ids from the loaded catalogues are added on top, so a new rule
becomes labelable as soon as its catalogue entry exists.
"""

from __future__ import annotations

from collections.abc import Mapping

MODULES = ("M1", "M2", "M3")

KNOWN_IDS: dict[str, tuple[str, ...]] = {
    "M1": tuple(f"S1.{i}" for i in range(1, 8)),
    "M2": ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12a", "R12b", "R13", "R14",
           "R15", "R16", "R17", "R18"),
    "M3": tuple(f"S3.{i}" for i in range(1, 9)),
}

#: Loaded catalogue per module: rule id -> implemented, or None when the build has no catalogue for it.
Catalogues = Mapping[str, Mapping[str, bool] | None]


def known_ids(catalogues: Catalogues) -> dict[str, set[str]]:
    return {m: set(KNOWN_IDS[m]) | set(catalogues.get(m) or {}) for m in MODULES}
