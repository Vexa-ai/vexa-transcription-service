from enum import Enum


class HTTPMethod(str, Enum):
    """HTTP-methods to requests."""

    HEAD = "HEAD"
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
