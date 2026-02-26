"""
PDF导入服务模块

提供后台队列任务，用于接收上传的PDF并增量写入SQLite数据库。
"""

from __future__ import annotations

import queue
import shutil
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
    target_dir: str
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
            "target_dir": self.target_dir,
            "relative_path": self.relative_path(),
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "summary": self.summary,
        }

    def relative_path(self) -> str:
        if not self.target_dir:
            return self.filename
        return f"{self.target_dir}/{self.filename}"


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
        upload_dir: Path | None = None,
        max_file_size_mb: int = 100,
        queue_size: int = 8,
        job_timeout_s: int = 600,
        max_jobs_retained: int = 1000,
        on_success: Callable[[], None] | None = None,
        db_write_lock: threading.Lock | None = None,
    ):
        self._db_path = db_path
        self._pdf_dir = pdf_dir
        self._upload_dir = upload_dir or pdf_dir
        self._max_file_size_bytes = max(1, int(max_file_size_mb)) * 1024 * 1024
        self._job_timeout_s = max(1, int(job_timeout_s))
        self._max_jobs_retained = max(1, int(max_jobs_retained))
        self._on_success = on_success
        self._db_write_lock = db_write_lock or threading.Lock()

        self._pdf_dir.mkdir(parents=True, exist_ok=True)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

        self._jobs: dict[str, ImportJob] = {}
        self._job_order: list[str] = []
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue(maxsize=max(1, int(queue_size)))
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run_worker, name="ipc-import-worker", daemon=True)
        self._worker.start()

    def submit_upload(
        self,
        filename: str,
        payload: bytes,
        content_type: str | None,
        target_dir: str = "",
    ) -> dict[str, Any]:
        """提交上传内容到导入队列"""
        safe_name = self._validate_and_normalize_filename(filename)
        safe_target_dir = self._normalize_target_dir(target_dir)
        self._validate_payload(payload, content_type)

        job_id = uuid.uuid4().hex
        staged_path = self._upload_dir / f"{job_id}__{safe_name}"
        staged_path.write_bytes(payload)

        job = ImportJob(
            id=job_id,
            filename=safe_name,
            path=staged_path,
            target_dir=safe_target_dir,
            status="queued",
            created_at=time.time(),
        )

        with self._lock:
            self._jobs[job_id] = job
            self._job_order.append(job_id)
            self._prune_jobs_locked()

        try:
            self._queue.put_nowait(job_id)
        except queue.Full as e:
            with self._lock:
                self._jobs[job_id].status = "failed"
                self._jobs[job_id].error = "import queue is full"
                self._jobs[job_id].finished_at = time.time()
                self._prune_jobs_locked()
            self._safe_unlink(staged_path)
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

    def _normalize_target_dir(self, target_dir: str) -> str:
        raw = (target_dir or "").replace("\\", "/").strip().strip("/")
        if not raw:
            return ""
        parts = [p for p in raw.split("/") if p]
        if any(p in {".", ".."} for p in parts):
            raise ValidationError("Invalid target_dir")
        return "/".join(parts)

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
        relative_path = job.relative_path()
        final_path = self._pdf_dir / relative_path
        backup_path: Path | None = None
        final_promoted = False
        try:
            backup_path = self._promote_uploaded_file(job.path, final_path)
            final_promoted = True

            with self._db_write_lock:
                with sqlite3.connect(str(self._db_path), timeout=60.0) as conn:
                    conn.row_factory = sqlite3.Row
                    try:
                        summary = ingest_pdfs(conn, [final_path], base_dir=self._pdf_dir)
                    except TypeError:
                        summary = ingest_pdfs(conn, [final_path])

            elapsed = time.time() - started
            with self._lock:
                job.status = "success"
                job.summary = {
                    **summary,
                    "relative_path": relative_path,
                    "elapsed_s": round(elapsed, 3),
                }
                job.finished_at = time.time()
                self._prune_jobs_locked()

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

            if backup_path is not None:
                self._safe_unlink(backup_path)

            logger.info(
                "Import job completed",
                extra_fields={"job_id": job_id, "elapsed_s": round(elapsed, 3)},
            )
        except Exception as e:
            with self._lock:
                job.status = "failed"
                job.error = str(e)
                job.finished_at = time.time()
                self._prune_jobs_locked()
            self._safe_unlink(job.path)
            if final_promoted:
                self._safe_unlink(final_path)
            self._restore_backup_file(backup_path, final_path)
            logger.exception(
                "Import job failed",
                extra_fields={"job_id": job_id},
            )

    def _promote_uploaded_file(self, staged_path: Path, final_path: Path) -> Path | None:
        """将上传暂存文件移动到最终PDF目录。"""
        final_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path: Path | None = None
        if final_path.exists():
            backup_path = self._make_backup_path(final_path)
            try:
                final_path.replace(backup_path)
            except OSError:
                shutil.move(str(final_path), str(backup_path))
        try:
            staged_path.replace(final_path)
        except OSError:
            # 跨设备移动时 replace 会失败，降级为 move。
            try:
                shutil.move(str(staged_path), str(final_path))
            except Exception:
                self._restore_backup_file(backup_path, final_path)
                raise
        except Exception:
            self._restore_backup_file(backup_path, final_path)
            raise
        return backup_path

    def _make_backup_path(self, final_path: Path) -> Path:
        return self._upload_dir / f".{final_path.name}.{uuid.uuid4().hex}.bak"

    def _restore_backup_file(self, backup_path: Path | None, final_path: Path) -> None:
        if backup_path is None or not backup_path.exists():
            return
        try:
            backup_path.replace(final_path)
        except OSError:
            shutil.move(str(backup_path), str(final_path))
        except Exception:
            logger.warning(
                "Failed to restore previous PDF file",
                extra_fields={"backup_path": str(backup_path), "final_path": str(final_path)},
            )

    def _safe_unlink(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            logger.warning(
                "Failed to cleanup temp upload file",
                extra_fields={"path": str(path)},
            )

    def delete_document(self, pdf_name: str) -> dict[str, Any]:
        """
        删除文档及其关联数据，并尝试删除对应 PDF 文件。

        返回结构:
        {
          "deleted": bool,
          "pdf_name": str,
          "deleted_counts": {"pages": int, "parts": int, "xrefs": int, "aliases": int},
          "file_deleted": bool,
        }
        """
        safe_identifier = self._normalize_pdf_identifier(pdf_name)
        safe_name = Path(safe_identifier).name
        with self._lock:
            for job_id in self._job_order:
                job = self._jobs.get(job_id)
                if not job:
                    continue
                if job.relative_path() == safe_identifier and job.status in {"queued", "running"}:
                    raise ValidationError("Document is being imported, please retry later")
                if job.filename == safe_name and job.status in {"queued", "running"}:
                    raise ValidationError("Document is being imported, please retry later")

        deleted_counts = {"pages": 0, "parts": 0, "xrefs": 0, "aliases": 0}
        raw_pdf_path = ""
        deleted = False

        with self._db_write_lock:
            with sqlite3.connect(str(self._db_path), timeout=60.0) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys=ON")
                row = conn.execute(
                    """
                    SELECT id, pdf_name, relative_path, pdf_path
                    FROM documents
                    WHERE relative_path = ? OR pdf_name = ?
                    ORDER BY CASE WHEN relative_path = ? THEN 0 ELSE 1 END
                    LIMIT 1
                    """,
                    (safe_identifier, safe_name, safe_identifier),
                ).fetchone()
                if row is None:
                    return {
                        "deleted": False,
                        "pdf_name": safe_name,
                        "deleted_counts": deleted_counts,
                        "file_deleted": False,
                    }

                doc_id = int(row["id"])
                safe_name = str(row["pdf_name"] or safe_name)
                raw_pdf_path = str(row["pdf_path"] or "")
                deleted_counts["pages"] = int(
                    conn.execute("SELECT COUNT(1) FROM pages WHERE document_id = ?", (doc_id,)).fetchone()[0]
                )
                deleted_counts["parts"] = int(
                    conn.execute("SELECT COUNT(1) FROM parts WHERE document_id = ?", (doc_id,)).fetchone()[0]
                )
                deleted_counts["xrefs"] = int(
                    conn.execute(
                        """
                        SELECT COUNT(1)
                        FROM xrefs x
                        JOIN parts p ON p.id = x.part_id
                        WHERE p.document_id = ?
                        """,
                        (doc_id,),
                    ).fetchone()[0]
                )
                deleted_counts["aliases"] = int(
                    conn.execute(
                        """
                        SELECT COUNT(1)
                        FROM aliases a
                        JOIN parts p ON p.id = a.part_id
                        WHERE p.document_id = ?
                        """,
                        (doc_id,),
                    ).fetchone()[0]
                )

                cur = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                conn.execute("DELETE FROM scan_state WHERE relative_path = ?", (safe_identifier,))
                conn.commit()
                deleted = cur.rowcount > 0

        file_deleted = False
        if deleted:
            file_deleted = self._delete_pdf_file(safe_identifier, raw_pdf_path)
            if self._on_success:
                try:
                    self._on_success()
                except Exception:
                    logger.exception("Delete success callback failed")
            logger.info(
                "Document deleted",
                extra_fields={
                    "pdf_name": safe_name,
                    "deleted_counts": deleted_counts,
                    "file_deleted": file_deleted,
                },
            )

        return {
            "deleted": deleted,
            "pdf_name": safe_name,
            "relative_path": safe_identifier,
            "deleted_counts": deleted_counts,
            "file_deleted": file_deleted,
        }

    def _normalize_pdf_identifier(self, value: str) -> str:
        raw = (value or "").replace("\\", "/").strip().strip("/")
        if not raw:
            raise ValidationError("Missing filename")
        parts = [p for p in raw.split("/") if p]
        if any(p in {".", ".."} for p in parts):
            raise ValidationError("Invalid filename")
        normalized = "/".join(parts)
        if not normalized.lower().endswith(".pdf"):
            raise ValidationError("Only .pdf files are supported")
        return normalized

    def _delete_pdf_file(self, pdf_name: str, raw_pdf_path: str) -> bool:
        for path in self._candidate_pdf_paths(pdf_name, raw_pdf_path):
            if not path.exists() or not path.is_file():
                continue
            try:
                path.unlink()
                return True
            except Exception:
                logger.warning(
                    "Failed to delete PDF file",
                    extra_fields={"pdf_name": pdf_name, "path": str(path)},
                )
        return False

    def _candidate_pdf_paths(self, pdf_name: str, raw_pdf_path: str) -> list[Path]:
        out: list[Path] = []
        seen: set[str] = set()

        def add(path: Path) -> None:
            if not self._is_within_dir(path, self._pdf_dir):
                return
            key = str(path)
            if key in seen:
                return
            seen.add(key)
            out.append(path)

        add(self._pdf_dir / pdf_name)
        raw = (raw_pdf_path or "").strip()
        if raw:
            raw_path = Path(raw)
            if raw_path.is_absolute():
                add(raw_path)
            else:
                add(self._pdf_dir / raw.replace("\\", "/"))

        return out

    @staticmethod
    def _is_within_dir(path: Path, base: Path) -> bool:
        try:
            path_resolved = path.resolve()
            base_resolved = base.resolve()
            return path_resolved == base_resolved or base_resolved in path_resolved.parents
        except Exception:
            return False

    def _prune_jobs_locked(self) -> None:
        if len(self._job_order) <= self._max_jobs_retained:
            return

        idx = 0
        while len(self._job_order) > self._max_jobs_retained and idx < len(self._job_order):
            job_id = self._job_order[idx]
            job = self._jobs.get(job_id)
            if job and job.status in {"success", "failed"}:
                self._job_order.pop(idx)
                self._jobs.pop(job_id, None)
                continue
            idx += 1
