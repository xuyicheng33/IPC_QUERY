"""
PDF 增量扫描服务

负责扫描 PDF 根目录，识别新增/变更文件并触发增量入库。
"""

from __future__ import annotations

import datetime as dt
import queue
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from build_db import ensure_schema, ingest_pdfs

from ..exceptions import ValidationError
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScanJob:
    """扫描任务状态"""

    id: str
    path: str
    status: str
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "path": self.path,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "summary": self.summary,
        }


class ScanService:
    """PDF 目录增量扫描服务（单 worker 串行执行）"""

    def __init__(
        self,
        db_path: Path,
        pdf_dir: Path,
        max_jobs_retained: int = 200,
        on_success: Callable[[], None] | None = None,
        db_write_lock: threading.Lock | None = None,
    ):
        self._db_path = db_path
        self._pdf_dir = pdf_dir
        self._max_jobs_retained = max(1, int(max_jobs_retained))
        self._on_success = on_success
        self._db_write_lock = db_write_lock or threading.Lock()

        self._jobs: dict[str, ScanJob] = {}
        self._job_order: list[str] = []
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue(maxsize=64)
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run_worker, name="ipc-scan-worker", daemon=True)
        self._worker.start()

    def submit_scan(self, path: str = "") -> dict[str, Any]:
        """提交扫描任务。path 为空表示扫描整个 pdf 根目录。"""
        safe_path = self._normalize_relative_dir(path)
        if safe_path:
            target = self._pdf_dir / safe_path
            if not target.exists() or not target.is_dir():
                raise ValidationError(f"Folder not found: {safe_path}")

        job_id = uuid.uuid4().hex
        job = ScanJob(
            id=job_id,
            path=safe_path,
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
                self._jobs[job_id].error = "scan queue is full"
                self._jobs[job_id].finished_at = time.time()
                self._prune_jobs_locked()
            raise ValidationError("Scan queue is full, please retry later") from e

        return job.to_dict()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.to_dict() if job else None

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            recent_ids = self._job_order[-max(1, int(limit)) :]
            out = [self._jobs[jid].to_dict() for jid in reversed(recent_ids) if jid in self._jobs]
        return out

    def stop(self, timeout_s: float = 2.0) -> None:
        self._stop_event.set()
        try:
            self._queue.put_nowait("__stop__")
        except queue.Full:
            pass
        self._worker.join(timeout=max(0.1, timeout_s))

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
            summary = self._scan_and_ingest(path=job.path)
            elapsed = time.time() - started
            with self._lock:
                job.status = "success"
                job.summary = {**summary, "elapsed_s": round(elapsed, 3)}
                job.finished_at = time.time()
                self._prune_jobs_locked()
            if self._on_success:
                self._on_success()
            logger.info(
                "Scan job completed",
                extra_fields={"job_id": job_id, "path": job.path, "elapsed_s": round(elapsed, 3)},
            )
        except Exception as e:
            with self._lock:
                job.status = "failed"
                job.error = str(e)
                job.finished_at = time.time()
                self._prune_jobs_locked()
            logger.exception("Scan job failed", extra_fields={"job_id": job_id, "path": job.path})

    def _scan_and_ingest(self, path: str) -> dict[str, Any]:
        base = self._pdf_dir / path if path else self._pdf_dir
        pdf_files = sorted(p for p in base.rglob("*.pdf") if p.is_file())

        entries: list[tuple[str, Path, int, float]] = []
        for abs_path in pdf_files:
            rel_path = abs_path.resolve().relative_to(self._pdf_dir.resolve()).as_posix()
            st = abs_path.stat()
            entries.append((rel_path, abs_path, int(st.st_size), float(st.st_mtime)))

        changed_paths: list[Path] = []
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat()

        with self._db_write_lock:
            with sqlite3.connect(str(self._db_path), timeout=60.0) as conn:
                conn.row_factory = sqlite3.Row
                ensure_schema(conn)

                if path:
                    prefix = f"{path}/%"
                    rows = conn.execute(
                        """
                        SELECT relative_path, size, mtime
                        FROM scan_state
                        WHERE relative_path = ? OR relative_path LIKE ?
                        """,
                        (path, prefix),
                    ).fetchall()
                else:
                    rows = conn.execute("SELECT relative_path, size, mtime FROM scan_state").fetchall()

                prev = {str(r["relative_path"]): (int(r["size"]), float(r["mtime"])) for r in rows}
                for rel_path, abs_path, size, mtime in entries:
                    old = prev.get(rel_path)
                    if old is None or old[0] != size or abs(old[1] - mtime) > 1e-9:
                        changed_paths.append(abs_path)

                ingest_summary: dict[str, int]
                if changed_paths:
                    try:
                        ingest_summary = ingest_pdfs(conn, changed_paths, base_dir=self._pdf_dir)
                    except TypeError:
                        ingest_summary = ingest_pdfs(conn, changed_paths)
                else:
                    ingest_summary = {
                        "docs_ingested": 0,
                        "docs_replaced": 0,
                        "parts_ingested": 0,
                        "xrefs_ingested": 0,
                        "aliases_ingested": 0,
                    }

                for rel_path, _abs_path, size, mtime in entries:
                    conn.execute(
                        """
                        INSERT INTO scan_state(relative_path, size, mtime, content_hash, updated_at)
                        VALUES (?, ?, ?, NULL, ?)
                        ON CONFLICT(relative_path) DO UPDATE SET
                          size=excluded.size,
                          mtime=excluded.mtime,
                          updated_at=excluded.updated_at
                        """,
                        (rel_path, size, mtime, now_iso),
                    )
                conn.commit()

        return {
            "path": path,
            "scanned_files": len(entries),
            "changed_files": len(changed_paths),
            **ingest_summary,
        }

    def _normalize_relative_dir(self, path: str) -> str:
        raw = (path or "").replace("\\", "/").strip().strip("/")
        if not raw:
            return ""
        parts = [p for p in raw.split("/") if p]
        if any(p in {".", ".."} for p in parts):
            raise ValidationError("Invalid path")
        return "/".join(parts)

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

