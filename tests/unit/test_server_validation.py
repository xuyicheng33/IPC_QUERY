"""
HTTP server 请求校验测试
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ipc_query.api.server import Server, _validated_content_length
from ipc_query.exceptions import ValidationError


def test_validated_content_length_accepts_within_limit() -> None:
    assert _validated_content_length("1024", max_file_size_mb=1) == 1024


def test_validated_content_length_rejects_invalid_header() -> None:
    with pytest.raises(ValidationError, match="Invalid Content-Length"):
        _validated_content_length("abc", max_file_size_mb=10)


def test_validated_content_length_rejects_oversized_body() -> None:
    with pytest.raises(ValidationError, match="File too large"):
        _validated_content_length(str(2 * 1024 * 1024), max_file_size_mb=1)


def test_server_stop_closes_socket_and_services() -> None:
    server = object.__new__(Server)
    mock_http_server = MagicMock()
    mock_import = MagicMock()
    mock_scan = MagicMock()
    mock_db = MagicMock()

    server._server = mock_http_server
    server._import = mock_import
    server._scan = mock_scan
    server._db = mock_db

    server.stop()

    mock_http_server.shutdown.assert_called_once_with()
    mock_http_server.server_close.assert_called_once_with()
    mock_import.stop.assert_called_once_with()
    mock_scan.stop.assert_called_once_with()
    mock_db.close_all.assert_called_once_with()
    assert server._server is None
