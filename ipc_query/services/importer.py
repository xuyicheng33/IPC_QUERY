"""
PDF导入服务模块

提供后台队列任务，用于接收上传的PDF并增量写入SQLite数据库。
"""

from __future__ import annotations

import queue
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from build_db import ingest_pdfs

from ..exceptions import ValidationError
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ImportJob:
    """导入任务状态"""

    id: str
    filename: str
    path: Path
    status: str
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "filename": self.filename,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "summary": self.summary,
        }


class ImportService:
    """
    PDF导入后台任务服务

    - 单线程worker处理入库任务
    - 通过有界队列限制并发提交
    """

    def __init__(
        self,
        db_path: Path,
        pdf_dir: Path,
        max_file_size_mb: int = 100,
        queue_size: int = 8,
        job_timeout_s: int = 600,
        on_success: Callable[[], None] | None = None,
    ):
        self._db_path = db_path
        self._pdf_dir = pdf_dir
        self._max_file_size_bytes = max(1, int(max_file_size_mb)) * 1024 * 1024
        self._job_timeout_s = max(1, int(job_timeout_s))
        self._on_success = on_success

        self._pdf_dir.mkdir(parents=True, exist_ok=True)

        self._jobs: dict[str, ImportJob] = {}
        self._job_order: list[str] = []
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue(maxsize=max(1, int(queue_size)))
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run_worker, name="ipc-import-worker", daemon=True)
        self._worker.start()

    def submit_upload(self, filename: str, payload: bytes, content_type: str | None) -> dict[str, Any]:
        """提交上传内容到导入队列"""
        safe_name = self._validate_and_normalize_filename(filename)
        self._validate_payload(payload, content_type)

        target_path = self._pdf_dir / safe_name
        target_path.write_bytes(payload)

        job_id = uuid.uuid4().hex
        job = ImportJob(
            id=job_id,
            filename=safe_name,
            path=target_path,
            status="queued",
            created_at=time.time(),
        )

        with self._lock:
            self._jobs[job_id] = job
            self._job_order.append(job_id)

        try:
            self._queue.put_nowait(job_id)
        except queue.Full as e:
            with self._lock:
                self._jobs[job_id].status = "failed"
                self._jobs[job_id].error = "import queue is full"
                self._jobs[job_id].finished_at = time.time()
            raise ValidationError("Import queue is full, please retry later") from e

        logger.info(
            "Import job queued",
            extra_fields={"job_id": job_id, "filename": safe_name},
        )
        return job.to_dict()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """获取任务状态"""
        with self._lock:
            job = self._jobs.get(job_id)
            return job.to_dict() if job else None

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        """列出最近任务"""
        with self._lock:
            recent_ids = self._job_order[-max(1, int(limit)) :]
            out = [self._jobs[jid].to_dict() for jid in reversed(recent_ids) if jid in self._jobs]
        return out

    def stop(self, timeout_s: float = 2.0) -> None:
        """停止后台worker"""
        self._stop_event.set()
        try:
            self._queue.put_nowait("__stop__")
        except queue.Full:
            pass
        self._worker.join(timeout=max(0.1, timeout_s))

    def _validate_and_normalize_filename(self, filename: str) -> str:
        safe_name = Path((filename or "").strip()).name
        if not safe_name:
            raise ValidationError("Missing filename")
        if not safe_name.lower().endswith(".pdf"):
            raise ValidationError("Only .pdf files are supported")
        return safe_name

    def _validate_payload(self, payload: bytes, content_type: str | None) -> None:
        if not payload:
            raise ValidationError("Empty file payload")
        if len(payload) > self._max_file_size_bytes:
            raise ValidationError(
                f"File too large (max {self._max_file_size_bytes // (1024 * 1024)}MB)"
            )

        ct = (content_type or "").strip().lower()
        if ct and ct not in {"application/pdf", "application/octet-stream"}:
            raise ValidationError(f"Unsupported content type: {ct}")

        if not payload.startswith(b"%PDF-"):
            raise ValidationError("Invalid PDF file signature")

    def _run_worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                job_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if job_id == "__stop__":
                self._queue.task_done()
                break

            self._run_one(job_id)
            self._queue.task_done()

    def _run_one(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "running"
            job.started_at = time.time()
            job.error = None

        started = time.time()
        try:
            with sqlite3.connect(str(self._db_path), timeout=60.0) as conn:
                conn.row_factory = sqlite3.Row
                summary = ingest_pdfs(conn, [job.path])

            elapsed = time.time() - started
            with self._lock:
                job.status = "success"
                job.summary = {
                    **summary,
                    "elapsed_s": round(elapsed, 3),
                }
                job.finished_at = time.time()

            if elapsed > self._job_timeout_s:
                logger.warning(
                    "Import job exceeded timeout budget",
                    extra_fields={"job_id": job_id, "elapsed_s": round(elapsed, 3)},
                )

            if self._on_success:
                try:
                    self._on_success()
                except Exception:
                    logger.exception("Import success callback failed")

            logger.info(
                "Import job completed",
                extra_fields={"job_id": job_id, "elapsed_s": round(elapsed, 3)},
            )
        except Exception as e:
            with self._lock:
                job.status = "failed"
                job.error = str(e)
                job.finished_at = time.time()
            logger.exception(
                "Import job failed",
                extra_fields={"job_id": job_id},
            )
