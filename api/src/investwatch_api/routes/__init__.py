"""REST routes, one module per resource of contracts/openapi.yaml, all under /api."""

from __future__ import annotations

from fastapi import FastAPI

from . import calibration, documents, findings, scans, settings, sources, stats


def register(api: FastAPI) -> None:
    for module in (findings, settings, stats, calibration, sources, scans, documents):
        api.include_router(module.router, prefix="/api")
