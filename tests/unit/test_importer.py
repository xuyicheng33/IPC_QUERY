"""
导入服务测试
"""

from __future__ import annotations

import queue
import time
from pathlib import Path

import pytest

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
