"""Bounded HTTPS implementation based on the Python standard library."""

from collections.abc import Mapping
from http.client import HTTPMessage
from types import TracebackType
from typing import IO, Optional, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from it_activity.ports.http import HttpResponse, HttpTransportError

MAX_RESPONSE_BYTES = 25 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 30.0


class _ReadableResponse(Protocol):
    def read(self, amount: int = -1) -> bytes:
        """Read at most the requested number of bytes."""


class _OpenedResponse(_ReadableResponse, Protocol):
    status: int
    headers: HTTPMessage

    def __enter__(self) -> "_OpenedResponse":
        """Enter the response context."""

    def __exit__(
        self,
        exception_type: Optional[type[BaseException]],
        exception: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        """Close the response context."""


class _NoRedirectHandler(HTTPRedirectHandler):
    """Prevent credential-bearing requests from changing origin."""

    def redirect_request(
        self,
        request: Request,
        file_pointer: IO[bytes],
        code: int,
        message: str,
        headers: HTTPMessage,
        new_url: str,
    ) -> Optional[Request]:
        return None


class UrllibHttpClient:
    """Perform bounded GET requests without automatic redirects."""

    def __init__(
        self,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
    ) -> None:
        if timeout_seconds <= 0 or max_response_bytes <= 0:
            raise ValueError("HTTP limits must be positive")
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._opener = build_opener(_NoRedirectHandler())

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        """Return a bounded response while redacting all transport failures."""
        try:
            parsed_url = urlsplit(url)
            if (
                parsed_url.scheme != "https"
                or not parsed_url.netloc
                or parsed_url.username is not None
                or parsed_url.password is not None
            ):
                raise HttpTransportError("Разрешены только HTTPS-запросы без credentials.")
            request = Request(url, headers=dict(headers), method="GET")  # noqa: S310
            opened = cast(
                _OpenedResponse,
                self._opener.open(request, timeout=self._timeout_seconds),
            )
            with opened as response:
                return HttpResponse(
                    status=response.status,
                    headers=dict(response.headers.items()),
                    body=self._read_bounded(response),
                )
        except HTTPError as error:
            return HttpResponse(
                status=error.code,
                headers={} if error.headers is None else dict(error.headers.items()),
                body=self._read_bounded(error),
            )
        except (HttpTransportError, OSError, URLError, ValueError):
            raise HttpTransportError("Внешний HTTP-запрос завершился ошибкой.") from None

    def _read_bounded(self, response: _ReadableResponse) -> bytes:
        body = response.read(self._max_response_bytes + 1)
        if len(body) > self._max_response_bytes:
            raise HttpTransportError("Ответ внешнего сервиса превышает допустимый размер.")
        return body
