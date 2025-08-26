class AgentException(Exception):
    """Base class for all agent-level errors."""

    pass


class InvalidTaskException(AgentException):
    """Raised when the task payload is malformed or incomplete."""

    pass


class DuplicateTaskException(AgentException):
    """Raised when a task with the same ID has already been registered."""

    pass


class UnsupportedOperationException(AgentException):
    """Raised when the agent does not support the requested operation."""

    pass


class AuthorizationException(AgentException):
    """Raised when authentication or authorization fails."""

    pass


class RateLimitExceededException(AgentException):
    """Raised when the agent rate-limits a request."""

    pass


class NoDataFoundException(AgentException):
    """Raised when requested data is not found."""

    pass


class ConflictException(AgentException):
    """Raised when data already exists and cannot be recreated."""

    pass


class InvalidDataException(AgentException):
    """Raised when provided data is semantically or structurally invalid."""

    pass


class TaskNotCancelableException(AgentException):
    pass


class PushNotificationNotSupportedException(AgentException):
    pass
