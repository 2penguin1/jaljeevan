from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (AppError, ConflictError, DomainValidationError, ExternalServiceError,
                                 NotFoundError)

_STATUS = {NotFoundError: 404, ConflictError: 409, DomainValidationError: 422, ExternalServiceError: 502}


def register_error_handlers(app: FastAPI) -> None:
    """Map application errors to HTTP once, so controllers and services never build HTTP responses."""

    async def handle(_request: Request, exc: AppError) -> JSONResponse:
        status = next((code for cls, code in _STATUS.items() if isinstance(exc, cls)), 500)
        return JSONResponse(status_code=status, content={"detail": str(exc)})

    app.add_exception_handler(AppError, handle)
