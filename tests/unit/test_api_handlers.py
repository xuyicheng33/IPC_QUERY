"""
API handlers 测试
"""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ipc_query.api.handlers import ApiHandlers
from ipc_query.config import Config
from ipc_query.exceptions import NotFoundError


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


def test_handle_pdf_reverse_range_returns_416(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    payload = b"0123456789"
    pdf_path.write_bytes(payload)
    handlers = _make_handlers(pdf_path)

    status, body, _, headers = handlers.handle_pdf("sample.pdf", "bytes=9-3")

    assert status == HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE
    assert body == b""
    assert headers["Content-Range"] == f"bytes */{len(payload)}"


def test_handle_doc_delete_success(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"0123")

    import_service = MagicMock()
    import_service.delete_document.return_value = {
        "deleted": True,
        "pdf_name": "sample.pdf",
        "deleted_counts": {"pages": 1, "parts": 2, "xrefs": 0, "aliases": 0},
        "file_deleted": True,
    }
    handlers = _make_handlers(pdf_path)
    handlers._import = import_service

    status, body, content_type = handlers.handle_doc_delete("sample.pdf")

    assert status == HTTPStatus.OK
    assert content_type == "application/json; charset=utf-8"
    data = json.loads(body.decode("utf-8"))
    assert data["deleted"] is True
    assert data["pdf_name"] == "sample.pdf"
    assert data["deleted_counts"]["parts"] == 2


def test_handle_doc_delete_not_found_raises(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"0123")

    import_service = MagicMock()
    import_service.delete_document.return_value = {
        "deleted": False,
        "pdf_name": "missing.pdf",
        "deleted_counts": {"pages": 0, "parts": 0, "xrefs": 0, "aliases": 0},
        "file_deleted": False,
    }
    handlers = _make_handlers(pdf_path)
    handlers._import = import_service

    with pytest.raises(NotFoundError):
        handlers.handle_doc_delete("missing.pdf")
