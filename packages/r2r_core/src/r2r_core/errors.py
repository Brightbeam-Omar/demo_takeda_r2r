"""Errors raised by event functions; the web layer maps them to HTTP status codes (F04-FR-10)."""


class EventError(Exception):
    """Base class for event failures."""


class Conflict(EventError):
    """A create that would duplicate a natural key. HTTP 409; nothing was written."""


class Invalid(EventError):
    """Unknown reference, code not in the profile, or an impossible state change. HTTP 422."""
