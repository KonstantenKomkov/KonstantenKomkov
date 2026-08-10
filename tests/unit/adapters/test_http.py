"""Tests for safe HTTP request boundaries."""

import pytest

from it_activity.adapters.http import UrllibHttpClient
from it_activity.ports.http import HttpTransportError


def test_http_client_rejects_non_https_url_without_network_access() -> None:
    client = UrllibHttpClient()

    with pytest.raises(HttpTransportError) as captured:
        client.get("http://private.example.invalid/path", {})

    assert "private.example.invalid" not in str(captured.value)
