"""REST routes, one module per resource of contracts/openapi.yaml."""

from __future__ import annotations

from fastapi import FastAPI


def register(api: FastAPI) -> None:
    import importlib

    for name in ("findings", "settings", "stats", "calibration", "sources", "scans", "documents"):
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"{__name__}.{name}":
                continue  # resource not implemented yet
            raise
        api.include_router(module.router, prefix="/api")
