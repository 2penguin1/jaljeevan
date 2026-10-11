from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import (AppError, ConflictError, DomainValidationError, ExternalServiceError, ForbiddenError,
                                 NotFoundError)

_STATUS = {NotFoundError: 404, ForbiddenError: 403, ConflictError: 409, DomainValidationError: 422, ExternalServiceError: 502}


def register_error_handlers(app: FastAPI) -> None:
    """Map application errors to HTTP once, so controllers and services never build HTTP responses."""

    async def handle(_request: Request, exc: AppError) -> JSONResponse:
        status = next((code for cls, code in _STATUS.items() if isinstance(exc, cls)), 500)
        return JSONResponse(status_code=status, content={"detail": str(exc)})

    async def invalid(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # never echo the input back: it may be a password, or a value JSON cannot hold (Infinity)
        errors = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", "invalid"), "type": e.get("type", "")}
                  for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    app.add_exception_handler(AppError, handle)
    app.add_exception_handler(RequestValidationError, invalid)
