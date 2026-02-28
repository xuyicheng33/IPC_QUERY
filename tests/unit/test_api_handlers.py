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
from ipc_query.exceptions import ConflictError
from ipc_query.exceptions import NotFoundError
from ipc_query.exceptions import ValidationError


def _make_handlers(
    pdf_path: Path,
    search_service: MagicMock | None = None,
    db: MagicMock | None = None,
    config: Config | None = None,
    *,
    import_enabled: bool | None = None,
    scan_enabled: bool | None = None,
    import_reason: str = "",
    scan_reason: str = "",
) -> ApiHandlers:
    render_service = MagicMock()
    render_service._find_pdf.return_value = pdf_path
    return ApiHandlers(
        search_service=search_service or MagicMock(),
        render_service=render_service,
        doc_repo=MagicMock(),
        db=db or MagicMock(),
        config=config or Config(),
        import_enabled=import_enabled,
        scan_enabled=scan_enabled,
        import_reason=import_reason,
        scan_reason=scan_reason,
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


def test_handle_doc_rename_success(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"0123")

    import_service = MagicMock()
    import_service.rename_document.return_value = {
        "updated": True,
        "old_path": "dir/a.pdf",
        "new_path": "dir/b.pdf",
        "pdf_name": "b.pdf",
    }
    handlers = _make_handlers(pdf_path)
    handlers._import = import_service

    status, body, content_type = handlers.handle_doc_rename(path="dir/a.pdf", new_name="b.pdf")

    assert status == HTTPStatus.OK
    assert content_type == "application/json; charset=utf-8"
    payload = json.loads(body.decode("utf-8"))
    assert payload["updated"] is True
    assert payload["new_path"] == "dir/b.pdf"


def test_handle_doc_rename_not_found_raises(tmp_path: Path) -> None:
    handlers = _make_handlers(tmp_path / "sample.pdf")
    handlers._import = MagicMock()
    handlers._import.rename_document.return_value = {"updated": False, "old_path": "missing.pdf", "new_path": "missing.pdf"}

    with pytest.raises(NotFoundError):
        handlers.handle_doc_rename(path="missing.pdf", new_name="new.pdf")


def test_handle_doc_move_success(tmp_path: Path) -> None:
    handlers = _make_handlers(tmp_path / "sample.pdf")
    handlers._import = MagicMock()
    handlers._import.move_document.return_value = {
        "updated": True,
        "old_path": "dir/a.pdf",
        "new_path": "archive/a.pdf",
        "pdf_name": "a.pdf",
    }

    status, body, content_type = handlers.handle_doc_move(path="dir/a.pdf", target_dir="archive")

    assert status == HTTPStatus.OK
    assert content_type == "application/json; charset=utf-8"
    payload = json.loads(body.decode("utf-8"))
    assert payload["updated"] is True
    assert payload["new_path"] == "archive/a.pdf"


def test_handle_capabilities_returns_reasons_when_disabled(tmp_path: Path) -> None:
    handlers = _make_handlers(
        tmp_path / "sample.pdf",
        import_enabled=False,
        scan_enabled=False,
        import_reason="import disabled by config",
        scan_reason="scan disabled by config",
    )

    status, body, content_type = handlers.handle_capabilities()

    assert status == HTTPStatus.OK
    assert content_type == "application/json; charset=utf-8"
    payload = json.loads(body.decode("utf-8"))
    assert payload["import_enabled"] is False
    assert payload["scan_enabled"] is False
    assert payload["import_reason"] == "import disabled by config"
    assert payload["scan_reason"] == "scan disabled by config"


def test_handle_docs_batch_delete_success(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"0123")

    import_service = MagicMock()
    import_service.delete_document.side_effect = [
        {
            "deleted": True,
            "pdf_name": "a.pdf",
            "relative_path": "a.pdf",
            "deleted_counts": {"pages": 1, "parts": 2, "xrefs": 0, "aliases": 0},
            "file_deleted": True,
        },
        {
            "deleted": True,
            "pdf_name": "b.pdf",
            "relative_path": "dir/b.pdf",
            "deleted_counts": {"pages": 0, "parts": 0, "xrefs": 0, "aliases": 0},
            "file_deleted": True,
        },
    ]
    handlers = _make_handlers(pdf_path)
    handlers._import = import_service

    status, body, content_type = handlers.handle_docs_batch_delete(["a.pdf", "dir/b.pdf"])

    assert status == HTTPStatus.OK
    assert content_type == "application/json; charset=utf-8"
    payload = json.loads(body.decode("utf-8"))
    assert payload["total"] == 2
    assert payload["deleted"] == 2
    assert payload["failed"] == 0
    assert [item["path"] for item in payload["results"]] == ["a.pdf", "dir/b.pdf"]
    assert all(item["ok"] is True for item in payload["results"])
    assert import_service.delete_document.call_count == 2


def test_handle_docs_batch_delete_partial_failure(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"0123")

    import_service = MagicMock()
    import_service.delete_document.side_effect = [
        {"deleted": True, "pdf_name": "a.pdf", "relative_path": "a.pdf"},
        {"deleted": False, "pdf_name": "missing.pdf", "relative_path": "missing.pdf"},
    ]
    handlers = _make_handlers(pdf_path)
    handlers._import = import_service

    status, body, _ = handlers.handle_docs_batch_delete(["a.pdf", "missing.pdf"])

    assert status == HTTPStatus.OK
    payload = json.loads(body.decode("utf-8"))
    assert payload["total"] == 2
    assert payload["deleted"] == 1
    assert payload["failed"] == 1
    assert payload["results"][0]["ok"] is True
    assert payload["results"][1]["ok"] is False
    assert "not found" in payload["results"][1]["error"].lower()
    assert payload["results"][1]["error_code"] == "NOT_FOUND"
    assert import_service.delete_document.call_count == 2


def test_handle_docs_batch_delete_conflict_includes_details(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"0123")

    import_service = MagicMock()
    import_service.delete_document.side_effect = ConflictError(
        "Ambiguous pdf name",
        details={"pdf_name": "a.pdf", "candidates": ["d1/a.pdf", "d2/a.pdf"]},
    )
    handlers = _make_handlers(pdf_path)
    handlers._import = import_service

    status, body, _ = handlers.handle_docs_batch_delete(["a.pdf"])

    assert status == HTTPStatus.OK
    payload = json.loads(body.decode("utf-8"))
    assert payload["failed"] == 1
    item = payload["results"][0]
    assert item["ok"] is False
    assert item["error_code"] == "CONFLICT"
    assert item["details"]["candidates"] == ["d1/a.pdf", "d2/a.pdf"]


def test_handle_docs_batch_delete_invalid_payload_raises(tmp_path: Path) -> None:
    handlers = _make_handlers(tmp_path / "sample.pdf")
    handlers._import = MagicMock()

    with pytest.raises(ValidationError):
        handlers.handle_docs_batch_delete("not-list")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        handlers.handle_docs_batch_delete([])


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
        sort="relevance",
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
        sort="relevance",
        page=1,
        page_size=20,
        include_notes=False,
        source_pdf="",
        source_dir="",
    )


def test_handle_search_page_size_uses_config_default(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    search_service = MagicMock()
    search_service.search.return_value = {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 33,
        "has_more": False,
        "match": "all",
    }
    handlers = _make_handlers(
        pdf_path,
        search_service=search_service,
        config=Config(default_page_size=33),
    )

    handlers.handle_search("q=abc&page=-9&page_size=-1&limit=-5")

    search_service.search.assert_called_once_with(
        query="abc",
        match="all",
        sort="relevance",
        page=1,
        page_size=33,
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
    handlers._docs.get_lookup_for_dir.return_value = (
        {"b.pdf": {"id": 1, "pdf_name": "b.pdf", "relative_path": "b.pdf", "relative_dir": ""}},
        {"b.pdf": {"id": 1, "pdf_name": "b.pdf", "relative_path": "b.pdf", "relative_dir": ""}},
    )

    status, body, _ = handlers.handle_docs_tree("")

    assert status == HTTPStatus.OK
    payload = json.loads(body.decode("utf-8"))
    assert payload["path"] == ""
    assert any(d["name"] == "sub" for d in payload["directories"])
    row = next(f for f in payload["files"] if f["name"] == "b.pdf")
    assert row["indexed"] is True


def test_handle_docs_tree_does_not_match_indexed_file_by_name_only(tmp_path: Path) -> None:
    pdf_root = tmp_path / "pdfs"
    (pdf_root / "1").mkdir(parents=True)
    (pdf_root / "1" / "review-folder").mkdir(parents=True)
    (pdf_root / "1" / "dup.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (pdf_root / "1" / "review-folder" / "dup.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")

    handlers = _make_handlers(tmp_path / "sample.pdf")
    handlers._config = Config(pdf_dir=pdf_root)
    handlers._docs.get_lookup_for_dir.return_value = (
        {
            "1/review-folder/dup.pdf": {
                "id": 2,
                "pdf_name": "dup.pdf",
                "relative_path": "1/review-folder/dup.pdf",
                "relative_dir": "1/review-folder",
            },
        },
        {"dup.pdf": {"id": 2, "pdf_name": "dup.pdf", "relative_path": "1/review-folder/dup.pdf"}},
    )

    status, body, _ = handlers.handle_docs_tree("1")

    assert status == HTTPStatus.OK
    payload = json.loads(body.decode("utf-8"))
    row = next(f for f in payload["files"] if f["name"] == "dup.pdf")
    assert row["relative_path"] == "1/dup.pdf"
    assert row["indexed"] is False
    assert row["document"] is None
    assert payload["directories"] == []


def test_handle_render_propagates_scale(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    handlers = _make_handlers(pdf_path)
    handlers._render.render_page.return_value = tmp_path / "render.png"

    status, body, ct = handlers.handle_render("sample.pdf", "1.png", "1.5")

    assert status == HTTPStatus.OK
    assert ct == "image/png"
    assert isinstance(body, Path)
    handlers._render.render_page.assert_called_once_with("sample.pdf", 1, scale=1.5)


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


def test_handle_folder_create_only_allows_root(tmp_path: Path) -> None:
    pdf_root = tmp_path / "pdfs"
    (pdf_root / "engine").mkdir(parents=True)
    handlers = _make_handlers(tmp_path / "sample.pdf")
    handlers._config = Config(pdf_dir=pdf_root)

    with pytest.raises(ValidationError):
        handlers.handle_folder_create(path="engine", name="sub")


def test_handle_folder_rename_success(tmp_path: Path) -> None:
    handlers = _make_handlers(tmp_path / "sample.pdf")
    handlers._import = MagicMock()
    handlers._import.rename_folder.return_value = {
        "updated": True,
        "old_path": "engine",
        "new_path": "engine-new",
        "renamed_docs": 2,
    }

    status, body, content_type = handlers.handle_folder_rename(path="engine", new_name="engine-new")

    assert status == HTTPStatus.OK
    assert content_type == "application/json; charset=utf-8"
    payload = json.loads(body.decode("utf-8"))
    assert payload["updated"] is True
    assert payload["new_path"] == "engine-new"


def test_handle_folder_delete_batch_success(tmp_path: Path) -> None:
    handlers = _make_handlers(tmp_path / "sample.pdf")
    handlers._import = MagicMock()
    handlers._import.delete_folder.side_effect = [
        {"deleted": True, "path": "a", "deleted_docs": 2},
        {"deleted": True, "path": "b", "deleted_docs": 0},
    ]

    status, body, content_type = handlers.handle_folder_delete(paths=["a", "b"], recursive=True)

    assert status == HTTPStatus.OK
    assert content_type == "application/json; charset=utf-8"
    payload = json.loads(body.decode("utf-8"))
    assert payload["total"] == 2
    assert payload["deleted"] == 2
    assert payload["failed"] == 0
    assert all(item["ok"] is True for item in payload["results"])


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


def test_handle_error_maps_conflict_to_409(tmp_path: Path) -> None:
    handlers = _make_handlers(tmp_path / "sample.pdf")
    status, body, content_type = handlers.handle_error(
        ConflictError("Ambiguous pdf name", details={"pdf_name": "a.pdf"})
    )

    assert status == HTTPStatus.CONFLICT
    assert content_type == "application/json"
    payload = json.loads(body.decode("utf-8"))
    assert payload["error"] == "CONFLICT"
