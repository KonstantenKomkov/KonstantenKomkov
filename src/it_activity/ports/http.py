"""Minimal HTTP port for the GitHub REST adapter."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


class HttpTransportError(RuntimeError):
    """A safe HTTP transport failure without URL or response contents."""


@dataclass(frozen=True)
class HttpResponse:
    """Raw response held only inside infrastructure adapters."""

    status: int
    headers: Mapping[str, str]
    body: bytes


class HttpClient(Protocol):
    """Perform a bounded HTTP GET request."""

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        """Return the response without logging request or response data."""
