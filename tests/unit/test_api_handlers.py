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


def _make_handlers(
    pdf_path: Path,
    search_service: MagicMock | None = None,
    db: MagicMock | None = None,
) -> ApiHandlers:
    render_service = MagicMock()
    render_service._find_pdf.return_value = pdf_path
    return ApiHandlers(
        search_service=search_service or MagicMock(),
        render_service=render_service,
        doc_repo=MagicMock(),
        db=db or MagicMock(),
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


def test_handle_search_normalizes_non_positive_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    search_service = MagicMock()
    search_service.search.return_value = {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 10,
        "has_more": False,
        "match": "pn",
    }
    handlers = _make_handlers(pdf_path, search_service=search_service)

    status, body, content_type = handlers.handle_search("q=abc&page=0&page_size=10&match=pn")

    assert status == HTTPStatus.OK
    assert content_type == "application/json; charset=utf-8"
    search_service.search.assert_called_once_with(
        query="abc",
        match="pn",
        page=1,
        page_size=10,
        include_notes=False,
        source_pdf="",
        source_dir="",
    )
    payload = json.loads(body.decode("utf-8"))
    assert payload["match"] == "pn"


def test_handle_search_page_size_falls_back_to_default_limit(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    search_service = MagicMock()
    search_service.search.return_value = {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 60,
        "has_more": False,
        "match": "all",
    }
    handlers = _make_handlers(pdf_path, search_service=search_service)

    handlers.handle_search("q=abc&page=-9&page_size=-1&limit=-5")

    search_service.search.assert_called_once_with(
        query="abc",
        match="all",
        page=1,
        page_size=60,
        include_notes=False,
        source_pdf="",
        source_dir="",
    )


def test_handle_health_propagates_healthy_status(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    db = MagicMock()
    db.check_health.return_value = {
        "status": "healthy",
        "parts_count": 10,
        "documents_count": 2,
    }
    handlers = _make_handlers(pdf_path, db=db)

    status, body, content_type = handlers.handle_health()

    assert status == HTTPStatus.OK
    assert content_type == "application/json; charset=utf-8"
    payload = json.loads(body.decode("utf-8"))
    assert payload["status"] == "healthy"
    assert payload["database"]["status"] == "healthy"


def test_handle_health_propagates_unhealthy_status(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    db = MagicMock()
    db.check_health.return_value = {
        "status": "unhealthy",
        "error": "database_error",
    }
    handlers = _make_handlers(pdf_path, db=db)

    status, body, content_type = handlers.handle_health()

    assert status == HTTPStatus.OK
    assert content_type == "application/json; charset=utf-8"
    payload = json.loads(body.decode("utf-8"))
    assert payload["status"] == "unhealthy"
    assert payload["database"]["status"] == "unhealthy"
    assert payload["database"]["error"] == "database_error"


def test_handle_docs_tree_lists_directories_and_files(tmp_path: Path) -> None:
    pdf_root = tmp_path / "pdfs"
    (pdf_root / "sub").mkdir(parents=True)
    (pdf_root / "sub" / "a.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (pdf_root / "b.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")

    handlers = _make_handlers(tmp_path / "sample.pdf")
    handlers._config = Config(pdf_dir=pdf_root)
    handlers._docs.get_all.return_value = [
        MagicMock(to_dict=lambda: {"id": 1, "pdf_name": "b.pdf", "relative_path": "b.pdf", "relative_dir": ""}),
    ]

    status, body, _ = handlers.handle_docs_tree("")

    assert status == HTTPStatus.OK
    payload = json.loads(body.decode("utf-8"))
    assert payload["path"] == ""
    assert any(d["name"] == "sub" for d in payload["directories"])
    row = next(f for f in payload["files"] if f["name"] == "b.pdf")
    assert row["indexed"] is True


def test_handle_folder_create_creates_dir(tmp_path: Path) -> None:
    pdf_root = tmp_path / "pdfs"
    pdf_root.mkdir(parents=True)
    handlers = _make_handlers(tmp_path / "sample.pdf")
    handlers._config = Config(pdf_dir=pdf_root)

    status, body, _ = handlers.handle_folder_create(path="", name="engine")

    assert status == HTTPStatus.CREATED
    payload = json.loads(body.decode("utf-8"))
    assert payload["created"] is True
    assert (pdf_root / "engine").exists()


def test_handle_scan_submit_calls_scan_service(tmp_path: Path) -> None:
    pdf_root = tmp_path / "pdfs"
    pdf_root.mkdir(parents=True)
    handlers = _make_handlers(tmp_path / "sample.pdf")
    handlers._config = Config(pdf_dir=pdf_root)
    handlers._scan = MagicMock()
    handlers._scan.submit_scan.return_value = {"job_id": "scan-1", "status": "queued"}

    status, body, _ = handlers.handle_scan_submit("sub")

    assert status == HTTPStatus.ACCEPTED
    payload = json.loads(body.decode("utf-8"))
    assert payload["job_id"] == "scan-1"
    handlers._scan.submit_scan.assert_called_once_with(path="sub")


def test_handle_scan_job_not_found_raises(tmp_path: Path) -> None:
    handlers = _make_handlers(tmp_path / "sample.pdf")
    handlers._scan = MagicMock()
    handlers._scan.get_job.return_value = None

    with pytest.raises(NotFoundError):
        handlers.handle_scan_job("missing")
