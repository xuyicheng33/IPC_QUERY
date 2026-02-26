"""
API handlers 测试
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from unittest.mock import MagicMock

from ipc_query.api.handlers import ApiHandlers
from ipc_query.config import Config


def _make_handlers(pdf_path: Path) -> ApiHandlers:
    render_service = MagicMock()
    render_service._find_pdf.return_value = pdf_path
    return ApiHandlers(
        search_service=MagicMock(),
        render_service=render_service,
        doc_repo=MagicMock(),
        db=MagicMock(),
        config=Config(),
    )


def test_handle_pdf_range_returns_partial_payload(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    payload = b"0123456789abcdef"
    pdf_path.write_bytes(payload)
    handlers = _make_handlers(pdf_path)

    status, body, content_type, headers = handlers.handle_pdf("sample.pdf", "bytes=3-7")

    assert status == HTTPStatus.PARTIAL_CONTENT
    assert body == payload[3:8]
    assert content_type == "application/pdf"
    assert headers["Content-Range"] == f"bytes 3-7/{len(payload)}"


def test_handle_pdf_invalid_range_returns_416(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    payload = b"0123456789"
    pdf_path.write_bytes(payload)
    handlers = _make_handlers(pdf_path)

    status, body, _, headers = handlers.handle_pdf("sample.pdf", "bytes=999-1000")

    assert status == HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE
    assert body == b""
    assert headers["Content-Range"] == f"bytes */{len(payload)}"
