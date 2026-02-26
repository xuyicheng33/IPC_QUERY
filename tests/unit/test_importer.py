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
from ipc_query.exceptions import ValidationError
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

        with pytest.raises(ValidationError):
            service.submit_upload("queue-full.pdf", _PDF_PAYLOAD, "application/pdf")

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
