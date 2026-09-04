class DartError(Exception):
    """Base error for the OpenDART boundary."""


class DartConfigurationError(DartError):
    """Raised when OpenDART credentials are unavailable or invalid locally."""


class DartResponseError(DartError):
    """Raised when OpenDART returns an invalid or unexpected payload."""


class DartApiError(DartError):
    def __init__(self, status: str, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"OpenDART error {status}: {message}")

    @property
    def retryable(self) -> bool:
        return self.status in {"020", "800", "900"}

