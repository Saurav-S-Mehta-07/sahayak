class SahayakError(Exception):
    """Base exception for expected application errors."""


class ServiceUnavailableError(SahayakError):
    """A required backend component is unavailable."""


class DocumentIngestionError(SahayakError):
    """A document could not be processed."""


class SessionNotFoundError(SahayakError):
    """The requested conversation session does not exist."""


class LLMServiceError(ServiceUnavailableError):
    """The configured language model could not produce a response."""
