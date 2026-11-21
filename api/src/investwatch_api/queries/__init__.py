"""SQL for the REST routes (SQLAlchemy Core, async). One module per resource."""

from __future__ import annotations

from sqlalchemy import case, literal

from ..db.tables import findings
from ..thresholds import MEDIUM_BAND, MODULES


def risk_level_expr(thresholds: dict[str, float]):
    """SQL CASE equal to thresholds.risk_level(score, threshold of the finding's module).

    The bounds are computed in Python and bound as parameters, so SQL and Python compare the same doubles.
    """
    high = case(*[(findings.c.module == m, literal(thresholds[m])) for m in MODULES])
    medium = case(*[(findings.c.module == m, literal(thresholds[m] - MEDIUM_BAND)) for m in MODULES])
    return case((findings.c.score >= high, "high"), (findings.c.score >= medium, "medium"), else_="low")


def like_pattern(needle: str) -> str:
    """Literal substring match for ILIKE ... ESCAPE '\\': %, _ and \\ are not wildcards."""
    escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
