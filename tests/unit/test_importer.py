"""
导入服务测试
"""

from __future__ import annotations

import queue
import sqlite3
import time
from pathlib import Path

import pytest

from build_db import ensure_schema
from ipc_query.exceptions import ConflictError, RateLimitError, ValidationError
from ipc_query.services import importer as importer_module
from ipc_query.services.importer import ImportService

_PDF_PAYLOAD = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _wait_for_terminal(service: ImportService, job_id: str, timeout_s: float = 2.0) -> dict | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        job = service.get_job(job_id)
        if job and job.get("status") in {"success", "failed"}:
            return job
        time.sleep(0.02)
    return service.get_job(job_id)


def test_submit_upload_queue_full_cleans_temp_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
        queue_size=1,
    )

    try:
        def _raise_full(_: str) -> None:
            raise queue.Full

        monkeypatch.setattr(service._queue, "put_nowait", _raise_full)

        with pytest.raises(RateLimitError) as exc:
            service.submit_upload("queue-full.pdf", _PDF_PAYLOAD, "application/pdf")
        assert exc.value.details.get("retry_after") == 3

        assert list((tmp_path / "uploads").glob("*.pdf")) == []
        jobs = service.list_jobs(limit=10)
        assert jobs
        assert jobs[0]["status"] == "failed"
        assert jobs[0]["error"] == "import queue is full"
    finally:
        service.stop()


def test_upload_dir_is_staging_and_pdf_dir_is_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_ingest(_conn: object, _pdf_paths: list[Path]) -> dict[str, int]:
        return {
            "docs_ingested": 1,
            "docs_replaced": 0,
            "parts_ingested": 0,
            "xrefs_ingested": 0,
            "aliases_ingested": 0,
        }

    monkeypatch.setattr(importer_module, "ingest_pdfs", _fake_ingest)

    upload_dir = tmp_path / "uploads"
    pdf_dir = tmp_path / "pdfs"
    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=pdf_dir,
        upload_dir=upload_dir,
        queue_size=4,
    )

    try:
        created = service.submit_upload("doc.pdf", _PDF_PAYLOAD, "application/pdf")
        job_id = str(created["job_id"])
        job = _wait_for_terminal(service, job_id)

        assert job is not None
        assert job["status"] == "success"
        assert (pdf_dir / "doc.pdf").exists()
        assert list(upload_dir.glob("*.pdf")) == []
    finally:
        service.stop()


def test_finished_jobs_are_pruned_by_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_ingest(_conn: object, _pdf_paths: list[Path]) -> dict[str, int]:
        return {
            "docs_ingested": 1,
            "docs_replaced": 0,
            "parts_ingested": 0,
            "xrefs_ingested": 0,
            "aliases_ingested": 0,
        }

    monkeypatch.setattr(importer_module, "ingest_pdfs", _fake_ingest)

    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
        queue_size=8,
        max_jobs_retained=3,
    )

    try:
        last_job_id = ""
        for idx in range(6):
            out = service.submit_upload(f"{idx}.pdf", _PDF_PAYLOAD, "application/pdf")
            last_job_id = str(out["job_id"])

        last_job = _wait_for_terminal(service, last_job_id, timeout_s=3.0)
        assert last_job is not None
        assert last_job["status"] == "success"

        jobs = service.list_jobs(limit=20)
        assert len(jobs) <= 3
        assert [j["filename"] for j in jobs] == ["5.pdf", "4.pdf", "3.pdf"]
    finally:
        service.stop()


def test_delete_document_removes_db_rows_and_pdf_file(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        doc_cur = conn.execute(
            "INSERT INTO documents(pdf_name, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, datetime('now'))",
            ("to-delete.pdf", "to-delete.pdf", "{}",),
        )
        doc_id = int(doc_cur.lastrowid)
        conn.execute(
            "INSERT INTO pages(document_id, page_num, figure_code) VALUES (?, ?, ?)",
            (doc_id, 1, "24-21-01"),
        )
        part_cur = conn.execute(
            "INSERT INTO parts(document_id, page_num, page_end, extractor, row_kind) VALUES (?, ?, ?, ?, ?)",
            (doc_id, 1, 1, "pdf_coords", "part"),
        )
        part_id = int(part_cur.lastrowid)
        conn.execute(
            "INSERT INTO xrefs(part_id, kind, target) VALUES (?, ?, ?)",
            (part_id, "DETAILS", "24-22-00"),
        )
        conn.execute(
            "INSERT INTO aliases(part_id, alias_type, alias_value) VALUES (?, ?, ?)",
            (part_id, "pn_alt", "ALT-1"),
        )
        conn.commit()

    (pdf_dir / "to-delete.pdf").write_bytes(_PDF_PAYLOAD)
    service = ImportService(
        db_path=db_path,
        pdf_dir=pdf_dir,
        upload_dir=upload_dir,
    )
    try:
        result = service.delete_document("to-delete.pdf")
        assert result["deleted"] is True
        assert result["file_deleted"] is True
        assert result["deleted_counts"]["pages"] == 1
        assert result["deleted_counts"]["parts"] == 1
        assert result["deleted_counts"]["xrefs"] == 1
        assert result["deleted_counts"]["aliases"] == 1

        with sqlite3.connect(str(db_path)) as conn:
            assert conn.execute("SELECT COUNT(1) FROM documents").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(1) FROM pages").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(1) FROM parts").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(1) FROM xrefs").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(1) FROM aliases").fetchone()[0] == 0
        assert not (pdf_dir / "to-delete.pdf").exists()
    finally:
        service.stop()


def test_delete_document_returns_deleted_false_when_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)

    service = ImportService(
        db_path=db_path,
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
    )
    try:
        result = service.delete_document("missing.pdf")
        assert result["deleted"] is False
        assert result["file_deleted"] is False
        assert result["deleted_counts"] == {"pages": 0, "parts": 0, "xrefs": 0, "aliases": 0}
    finally:
        service.stop()


def test_delete_document_by_relative_path_is_exact(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    (pdf_dir / "dir1").mkdir(parents=True, exist_ok=True)
    (pdf_dir / "dir2").mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("same-dir1.pdf", "dir1/same.pdf", "dir1/same.pdf", "{}"),
        )
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("same-dir2.pdf", "dir2/same.pdf", "dir2/same.pdf", "{}"),
        )
        conn.commit()

    (pdf_dir / "dir1" / "same.pdf").write_bytes(_PDF_PAYLOAD)
    (pdf_dir / "dir2" / "same.pdf").write_bytes(_PDF_PAYLOAD)
    service = ImportService(db_path=db_path, pdf_dir=pdf_dir, upload_dir=upload_dir)
    try:
        result = service.delete_document("dir1/same.pdf")
        assert result["deleted"] is True
        assert result["relative_path"] == "dir1/same.pdf"
        assert not (pdf_dir / "dir1" / "same.pdf").exists()
        assert (pdf_dir / "dir2" / "same.pdf").exists()
    finally:
        service.stop()


def test_delete_document_prefers_exact_root_relative_path(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    (pdf_dir / "test").mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("same.pdf", "same.pdf", "same.pdf", "{}"),
        )
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("same.pdf", "test/same.pdf", "test/same.pdf", "{}"),
        )
        conn.commit()

    (pdf_dir / "same.pdf").write_bytes(_PDF_PAYLOAD)
    (pdf_dir / "test" / "same.pdf").write_bytes(_PDF_PAYLOAD)
    service = ImportService(db_path=db_path, pdf_dir=pdf_dir, upload_dir=upload_dir)
    try:
        result = service.delete_document("same.pdf")
        assert result["deleted"] is True
        assert result["relative_path"] == "same.pdf"
        assert not (pdf_dir / "same.pdf").exists()
        assert (pdf_dir / "test" / "same.pdf").exists()
    finally:
        service.stop()


def test_delete_document_basename_conflict_raises(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    (pdf_dir / "dir1").mkdir(parents=True, exist_ok=True)
    (pdf_dir / "dir2").mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        # 使用无 UNIQUE(pdf_name) 约束的最小 schema，模拟历史库中同名文档并存。
        conn.executescript(
            """
            CREATE TABLE documents (
              id INTEGER PRIMARY KEY,
              pdf_name TEXT NOT NULL,
              relative_path TEXT NOT NULL,
              pdf_path TEXT NOT NULL,
              miner_dir TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE pages (
              id INTEGER PRIMARY KEY,
              document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              page_num INTEGER NOT NULL
            );
            CREATE TABLE parts (
              id INTEGER PRIMARY KEY,
              document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              page_num INTEGER NOT NULL,
              page_end INTEGER NOT NULL,
              extractor TEXT NOT NULL,
              row_kind TEXT NOT NULL
            );
            CREATE TABLE xrefs (
              id INTEGER PRIMARY KEY,
              part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
              kind TEXT NOT NULL,
              target TEXT NOT NULL
            );
            CREATE TABLE aliases (
              id INTEGER PRIMARY KEY,
              part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
              alias_type TEXT NOT NULL DEFAULT '',
              alias_value TEXT NOT NULL
            );
            CREATE TABLE scan_state (
              relative_path TEXT PRIMARY KEY,
              size INTEGER NOT NULL,
              mtime REAL NOT NULL,
              content_hash TEXT,
              updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("same.pdf", "dir1/same.pdf", "dir1/same.pdf", "{}"),
        )
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("same.pdf", "dir2/same.pdf", "dir2/same.pdf", "{}"),
        )
        conn.commit()

    service = ImportService(db_path=db_path, pdf_dir=pdf_dir, upload_dir=upload_dir)
    try:
        with pytest.raises(ConflictError) as exc:
            service.delete_document("same.pdf")
        assert exc.value.code == "CONFLICT"
        assert exc.value.details.get("candidates") == ["dir1/same.pdf", "dir2/same.pdf"]
    finally:
        service.stop()


def test_failed_ingest_cleans_new_pdf_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_ingest(_conn: object, _pdf_paths: list[Path]) -> dict[str, int]:
        raise RuntimeError("ingest failed")

    monkeypatch.setattr(importer_module, "ingest_pdfs", _raise_ingest)

    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=pdf_dir,
        upload_dir=upload_dir,
    )
    try:
        created = service.submit_upload("failed.pdf", _PDF_PAYLOAD, "application/pdf")
        job_id = str(created["job_id"])
        job = _wait_for_terminal(service, job_id)
        assert job is not None
        assert job["status"] == "failed"
        assert not (pdf_dir / "failed.pdf").exists()
        assert list(upload_dir.glob("*failed.pdf")) == []
    finally:
        service.stop()


def test_failed_ingest_restores_previous_pdf_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_ingest(_conn: object, _pdf_paths: list[Path]) -> dict[str, int]:
        raise RuntimeError("ingest failed")

    monkeypatch.setattr(importer_module, "ingest_pdfs", _raise_ingest)

    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    original_payload = b"%PDF-1.4\noriginal\n%%EOF\n"
    replaced_payload = b"%PDF-1.4\nreplacement\n%%EOF\n"
    target = pdf_dir / "same.pdf"
    target.write_bytes(original_payload)

    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=pdf_dir,
        upload_dir=upload_dir,
    )
    try:
        created = service.submit_upload("same.pdf", replaced_payload, "application/pdf")
        job_id = str(created["job_id"])
        job = _wait_for_terminal(service, job_id)
        assert job is not None
        assert job["status"] == "failed"
        assert target.exists()
        assert target.read_bytes() == original_payload
        assert [p for p in upload_dir.iterdir() if p.suffix == ".bak"] == []
    finally:
        service.stop()


def test_submit_upload_validation_errors(tmp_path: Path) -> None:
    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
        max_file_size_mb=1,
    )
    try:
        with pytest.raises(ValidationError, match="Missing filename"):
            service.submit_upload("", _PDF_PAYLOAD, "application/pdf")
        with pytest.raises(ValidationError, match="Only .pdf files are supported"):
            service.submit_upload("bad.txt", _PDF_PAYLOAD, "application/pdf")
        with pytest.raises(ValidationError, match="Empty file payload"):
            service.submit_upload("empty.pdf", b"", "application/pdf")
        with pytest.raises(ValidationError, match="File too large"):
            service.submit_upload("large.pdf", b"%PDF-" + b"a" * (2 * 1024 * 1024), "application/pdf")
        with pytest.raises(ValidationError, match="Unsupported content type"):
            service.submit_upload("ct.pdf", _PDF_PAYLOAD, "text/plain")
        with pytest.raises(ValidationError, match="Invalid PDF file signature"):
            service.submit_upload("sig.pdf", b"bad", "application/pdf")
    finally:
        service.stop()


def test_run_one_missing_job_is_noop(tmp_path: Path) -> None:
    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
    )
    try:
        service._run_one("missing-job")
    finally:
        service.stop()


def test_on_success_callback_failure_keeps_success_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_ingest(_conn: object, _pdf_paths: list[Path]) -> dict[str, int]:
        return {
            "docs_ingested": 1,
            "docs_replaced": 0,
            "parts_ingested": 0,
            "xrefs_ingested": 0,
            "aliases_ingested": 0,
        }

    monkeypatch.setattr(importer_module, "ingest_pdfs", _fake_ingest)

    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
        on_success=lambda: (_ for _ in ()).throw(RuntimeError("callback failed")),
    )
    try:
        created = service.submit_upload("ok.pdf", _PDF_PAYLOAD, "application/pdf")
        job = _wait_for_terminal(service, str(created["job_id"]))
        assert job is not None
        assert job["status"] == "success"
    finally:
        service.stop()


def test_delete_document_rejects_when_job_is_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _slow_ingest(_conn: object, _pdf_paths: list[Path]) -> dict[str, int]:
        time.sleep(0.2)
        return {
            "docs_ingested": 1,
            "docs_replaced": 0,
            "parts_ingested": 0,
            "xrefs_ingested": 0,
            "aliases_ingested": 0,
        }

    monkeypatch.setattr(importer_module, "ingest_pdfs", _slow_ingest)
    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
    )
    try:
        created = service.submit_upload("busy.pdf", _PDF_PAYLOAD, "application/pdf")
        with pytest.raises(ValidationError, match="being imported"):
            service.delete_document("busy.pdf")
        _wait_for_terminal(service, str(created["job_id"]), timeout_s=3.0)
    finally:
        service.stop()


def test_delete_document_callback_failure_does_not_break_delete(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, datetime('now'))",
            ("cb-fail.pdf", "cb-fail.pdf", "{}",),
        )
        conn.commit()

    (pdf_dir / "cb-fail.pdf").write_bytes(_PDF_PAYLOAD)
    service = ImportService(
        db_path=db_path,
        pdf_dir=pdf_dir,
        upload_dir=upload_dir,
        on_success=lambda: (_ for _ in ()).throw(RuntimeError("callback failed")),
    )
    try:
        result = service.delete_document("cb-fail.pdf")
        assert result["deleted"] is True
    finally:
        service.stop()


def test_candidate_pdf_paths_filters_outside_paths(tmp_path: Path) -> None:
    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
    )
    try:
        outside = (tmp_path / "outside.pdf").resolve()
        inside_abs = (service._pdf_dir / "inside.pdf").resolve()
        paths = service._candidate_pdf_paths("inside.pdf", str(outside))
        assert inside_abs in [p.resolve() for p in paths]
        assert outside not in [p.resolve() for p in paths]
    finally:
        service.stop()


def test_delete_pdf_file_returns_false_when_unlink_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
    )
    target = service._pdf_dir / "bad-delete.pdf"
    target.write_bytes(_PDF_PAYLOAD)

    original_unlink = Path.unlink

    def _broken_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self.resolve() == target.resolve():
            raise OSError("cannot delete")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _broken_unlink)
    try:
        assert service._delete_pdf_file("bad-delete.pdf", "") is False
    finally:
        service.stop()


def test_rename_document_updates_file_db_and_scan_state(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    (pdf_dir / "dir").mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("a.pdf", "dir/a.pdf", "dir/a.pdf", "{}"),
        )
        conn.execute(
            "INSERT INTO scan_state(relative_path, size, mtime, content_hash, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("dir/a.pdf", 10, 1.0, "h1"),
        )
        conn.commit()

    (pdf_dir / "dir" / "a.pdf").write_bytes(_PDF_PAYLOAD)
    service = ImportService(db_path=db_path, pdf_dir=pdf_dir, upload_dir=upload_dir)
    try:
        result = service.rename_document("dir/a.pdf", "b.pdf")
        assert result["updated"] is True
        assert result["old_path"] == "dir/a.pdf"
        assert result["new_path"] == "dir/b.pdf"
        assert result["pdf_name"] == "b.pdf"
        assert not (pdf_dir / "dir" / "a.pdf").exists()
        assert (pdf_dir / "dir" / "b.pdf").exists()

        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT pdf_name, relative_path, pdf_path FROM documents WHERE relative_path = ?",
                ("dir/b.pdf",),
            ).fetchone()
            assert row is not None
            assert row["pdf_name"] == "b.pdf"
            assert row["relative_path"] == "dir/b.pdf"
            assert row["pdf_path"] == "dir/b.pdf"
            assert conn.execute(
                "SELECT COUNT(1) FROM scan_state WHERE relative_path = ?",
                ("dir/a.pdf",),
            ).fetchone()[0] == 0
            assert conn.execute(
                "SELECT COUNT(1) FROM scan_state WHERE relative_path = ?",
                ("dir/b.pdf",),
            ).fetchone()[0] == 1
    finally:
        service.stop()


def test_move_document_updates_file_and_db(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    (pdf_dir / "dir").mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("a.pdf", "dir/a.pdf", "dir/a.pdf", "{}"),
        )
        conn.commit()

    (pdf_dir / "dir" / "a.pdf").write_bytes(_PDF_PAYLOAD)
    service = ImportService(db_path=db_path, pdf_dir=pdf_dir, upload_dir=upload_dir)
    try:
        result = service.move_document("dir/a.pdf", "other")
        assert result["updated"] is True
        assert result["old_path"] == "dir/a.pdf"
        assert result["new_path"] == "other/a.pdf"
        assert result["pdf_name"] == "a.pdf"
        assert not (pdf_dir / "dir" / "a.pdf").exists()
        assert (pdf_dir / "other" / "a.pdf").exists()

        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT pdf_name, relative_path, pdf_path FROM documents WHERE relative_path = ?",
                ("other/a.pdf",),
            ).fetchone()
            assert row is not None
            assert row["pdf_name"] == "a.pdf"
            assert row["relative_path"] == "other/a.pdf"
            assert row["pdf_path"] == "other/a.pdf"
    finally:
        service.stop()


def test_move_document_rejects_nested_target_dir(tmp_path: Path) -> None:
    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
    )
    try:
        with pytest.raises(ValidationError, match="Only top-level target_dir"):
            service.move_document("a.pdf", "nested/path")
    finally:
        service.stop()


def test_rename_folder_updates_files_db_and_scan_state(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    (pdf_dir / "engine").mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("a.pdf", "engine/a.pdf", "engine/a.pdf", "{}"),
        )
        conn.execute(
            "INSERT INTO scan_state(relative_path, size, mtime, content_hash, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("engine/a.pdf", 1, 1.0, "h1"),
        )
        conn.commit()

    (pdf_dir / "engine" / "a.pdf").write_bytes(_PDF_PAYLOAD)
    service = ImportService(db_path=db_path, pdf_dir=pdf_dir, upload_dir=upload_dir)
    try:
        result = service.rename_folder("engine", "engine-new")
        assert result["updated"] is True
        assert result["old_path"] == "engine"
        assert result["new_path"] == "engine-new"
        assert (pdf_dir / "engine-new" / "a.pdf").exists()
        assert not (pdf_dir / "engine").exists()

        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT pdf_name, relative_path, pdf_path FROM documents WHERE relative_path = ?",
                ("engine-new/a.pdf",),
            ).fetchone()
            assert row is not None
            assert row[0] == "a.pdf"
            assert row[1] == "engine-new/a.pdf"
            assert row[2] == "engine-new/a.pdf"
            assert conn.execute(
                "SELECT COUNT(1) FROM scan_state WHERE relative_path = ?",
                ("engine-new/a.pdf",),
            ).fetchone()[0] == 1
    finally:
        service.stop()


def test_delete_folder_recursive_removes_db_and_files(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    (pdf_dir / "engine").mkdir(parents=True, exist_ok=True)
    (pdf_dir / "engine" / "a.pdf").write_bytes(_PDF_PAYLOAD)
    (pdf_dir / "engine" / "b.pdf").write_bytes(_PDF_PAYLOAD)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("a.pdf", "engine/a.pdf", "engine/a.pdf", "{}"),
        )
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("b.pdf", "engine/b.pdf", "engine/b.pdf", "{}"),
        )
        conn.execute(
            "INSERT INTO scan_state(relative_path, size, mtime, content_hash, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("engine/a.pdf", 1, 1.0, "h1"),
        )
        conn.execute(
            "INSERT INTO scan_state(relative_path, size, mtime, content_hash, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("engine/b.pdf", 1, 1.0, "h2"),
        )
        conn.commit()

    service = ImportService(db_path=db_path, pdf_dir=pdf_dir, upload_dir=upload_dir)
    try:
        result = service.delete_folder("engine", recursive=True)
        assert result["deleted"] is True
        assert result["path"] == "engine"
        assert result["deleted_docs"] == 2
        assert result["deleted_scan_state"] == 2
        assert result["folder_deleted"] is True
        assert not (pdf_dir / "engine").exists()

        with sqlite3.connect(str(db_path)) as conn:
            assert conn.execute("SELECT COUNT(1) FROM documents").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(1) FROM scan_state").fetchone()[0] == 0
    finally:
        service.stop()


def test_folder_ops_only_allow_top_level_path(tmp_path: Path) -> None:
    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
    )
    try:
        with pytest.raises(ValidationError, match="top-level"):
            service.rename_folder("a/b", "x")
        with pytest.raises(ValidationError, match="top-level"):
            service.delete_folder("a/b", recursive=True)
    finally:
        service.stop()


def test_rename_document_conflict_raises(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    (pdf_dir / "dir").mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("a.pdf", "dir/a.pdf", "dir/a.pdf", "{}"),
        )
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("b.pdf", "dir/b.pdf", "dir/b.pdf", "{}"),
        )
        conn.commit()

    (pdf_dir / "dir" / "a.pdf").write_bytes(_PDF_PAYLOAD)
    (pdf_dir / "dir" / "b.pdf").write_bytes(_PDF_PAYLOAD)
    service = ImportService(db_path=db_path, pdf_dir=pdf_dir, upload_dir=upload_dir)
    try:
        with pytest.raises(ConflictError):
            service.rename_document("dir/a.pdf", "b.pdf")
    finally:
        service.stop()


def test_rename_and_move_reject_when_source_job_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _slow_ingest(_conn: object, _pdf_paths: list[Path]) -> dict[str, int]:
        time.sleep(0.2)
        return {
            "docs_ingested": 1,
            "docs_replaced": 0,
            "parts_ingested": 0,
            "xrefs_ingested": 0,
            "aliases_ingested": 0,
        }

    monkeypatch.setattr(importer_module, "ingest_pdfs", _slow_ingest)
    service = ImportService(
        db_path=tmp_path / "db.sqlite",
        pdf_dir=tmp_path / "pdfs",
        upload_dir=tmp_path / "uploads",
    )
    try:
        created = service.submit_upload("busy.pdf", _PDF_PAYLOAD, "application/pdf")
        with pytest.raises(ValidationError, match="being imported"):
            service.rename_document("busy.pdf", "renamed.pdf")
        with pytest.raises(ValidationError, match="being imported"):
            service.move_document("busy.pdf", "archive")
        _wait_for_terminal(service, str(created["job_id"]), timeout_s=3.0)
    finally:
        service.stop()
