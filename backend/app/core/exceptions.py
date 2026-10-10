"""Application error hierarchy. Mapped to HTTP status codes once, in api/error_handlers.py."""


class AppError(Exception):
    """Base class for every error the application raises on purpose."""


class NotFoundError(AppError):
    """A requested record does not exist (HTTP 404)."""


class ConflictError(AppError):
    """An illegal state transition or a stale update (HTTP 409)."""


class DomainValidationError(AppError):
    """Input violates a business rule (HTTP 422)."""


class ExternalServiceError(AppError):
    """An outside system (GDELT, Apify, Bedrock, ...) failed. `retryable` tells callers whether to try again."""

    def __init__(self, service: str, message: str, retryable: bool = True):
        super().__init__(f"{service}: {message}")
        self.service = service
        self.retryable = retryable
