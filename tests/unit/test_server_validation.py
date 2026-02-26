"""
HTTP server 请求校验测试
"""

from __future__ import annotations

import pytest

from ipc_query.api.server import _validated_content_length
from ipc_query.exceptions import ValidationError


def test_validated_content_length_accepts_within_limit() -> None:
    assert _validated_content_length("1024", max_file_size_mb=1) == 1024


def test_validated_content_length_rejects_invalid_header() -> None:
    with pytest.raises(ValidationError, match="Invalid Content-Length"):
        _validated_content_length("abc", max_file_size_mb=10)


def test_validated_content_length_rejects_oversized_body() -> None:
    with pytest.raises(ValidationError, match="File too large"):
        _validated_content_length(str(2 * 1024 * 1024), max_file_size_mb=1)
