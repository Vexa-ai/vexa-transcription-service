"""Errors of Redis module."""


class RedisBaseError(Exception):
    """Base Redis error."""

    pass


class RedisConnectionError(RedisBaseError):
    """Redis database connection error (wrong config, broken database, etc.)."""

    pass


class CommandExecuteError(RedisBaseError):
    """Redis command (get, set, etc.) error."""

    pass


class DataNotFoundError(RedisBaseError):
    """ToDo."""

    pass


class UserTokenAlreadyExist(RedisBaseError):
    pass
