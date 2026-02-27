from __future__ import annotations

import sqlite3
from pathlib import Path

from build_db import ensure_schema
from ipc_query.services.scanner import ScanService


def test_scan_removes_deleted_documents_and_scan_state(tmp_path: Path) -> None:
    db_path = tmp_path / "scan.sqlite"
    pdf_dir = tmp_path / "pdfs"
    (pdf_dir / "engine").mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("stale.pdf", "engine/stale.pdf", "engine/stale.pdf", "{}"),
        )
        conn.execute(
            "INSERT INTO scan_state(relative_path, size, mtime, content_hash, updated_at) VALUES (?, ?, ?, NULL, datetime('now'))",
            ("engine/stale.pdf", 123, 123.0),
        )
        conn.commit()

    service = ScanService(db_path=db_path, pdf_dir=pdf_dir)
    try:
        summary = service._scan_and_ingest(path="engine")
    finally:
        service.stop()

    assert summary["scanned_files"] == 0
    assert summary["changed_files"] == 0
    assert summary["deleted_files"] == 1
    assert summary["docs_deleted"] == 1

    with sqlite3.connect(str(db_path)) as conn:
        docs_left = conn.execute("SELECT COUNT(1) FROM documents").fetchone()[0]
        scan_state_left = conn.execute("SELECT COUNT(1) FROM scan_state").fetchone()[0]
        assert docs_left == 0
        assert scan_state_left == 0
