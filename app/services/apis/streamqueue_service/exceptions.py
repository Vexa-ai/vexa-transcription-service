"""Exceptions of StreamQueue-service module."""


class StreamQueueServiceBaseError(Exception):
    """Base service error."""

    pass


class StreamQueueServiceRequestError(StreamQueueServiceBaseError):
    """Request error (http statuses 4** and 5**)."""

    pass


class StreamQueueServiceTimeoutError(StreamQueueServiceBaseError):
    """Base service error."""

    pass
