"""Error bodies in the contract shape {"error": ..., "details": ...} (contracts/openapi.yaml components.schemas.Error).

Copied from the archived mock server's exception handlers (design decision 2).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ServiceUnavailable(Exception):
    """A dependency (Redis, MinIO) is needed for this request and is down: 503 with an error body."""

    def __init__(self, dependency: str):
        super().__init__(dependency)
        self.dependency = dependency


def validation_error(loc: list, msg: str) -> RequestValidationError:
    return RequestValidationError([{"loc": loc, "msg": msg}])


def install(api: FastAPI) -> None:
    @api.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)

    @api.exception_handler(RequestValidationError)
    async def request_validation_error(_: Request, exc: RequestValidationError):
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse({"error": "validation_error", "details": details}, status_code=422)

    @api.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        # Contract error shape for anything unforeseen (database down, driver errors); only the class is logged.
        logging.getLogger("investwatch_api").error("unhandled error", extra={"reason": type(exc).__name__})
        return JSONResponse({"error": "internal error"}, status_code=500)

    @api.exception_handler(ServiceUnavailable)
    async def service_unavailable(_: Request, exc: ServiceUnavailable):
        return JSONResponse({"error": f"{exc.dependency} unavailable"}, status_code=503)
