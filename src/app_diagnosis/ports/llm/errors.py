class LLMError(RuntimeError):
    """Base language-model port error safe for application-level handling."""


class LLMTimeoutError(LLMError):
    pass


class LLMTransportError(LLMError):
    pass


class LLMProtocolError(LLMError):
    pass


class LLMHTTPError(LLMError):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.retryable = status_code in {408, 409, 429} or status_code >= 500
        super().__init__(f"model endpoint returned HTTP {status_code}: {message}")
