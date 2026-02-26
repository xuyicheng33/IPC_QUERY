"""
数据库连接模块测试
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ipc_query.db.connection import Database


def _init_health_schema(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                pdf_name TEXT
            );
            CREATE TABLE parts (
                id INTEGER PRIMARY KEY,
                document_id INTEGER
            );
            """
        )
        conn.execute("INSERT INTO documents(id, pdf_name) VALUES (1, 'a.pdf')")
        conn.execute("INSERT INTO documents(id, pdf_name) VALUES (2, 'b.pdf')")
        conn.execute("INSERT INTO parts(id, document_id) VALUES (1, 1)")
        conn.execute("INSERT INTO parts(id, document_id) VALUES (2, 1)")
        conn.execute("INSERT INTO parts(id, document_id) VALUES (3, 2)")
        conn.commit()
    finally:
        conn.close()


def test_check_health_returns_counts_when_schema_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "health.sqlite"
    _init_health_schema(db_path)
    db = Database(db_path, readonly=True)

    result = db.check_health()

    assert result["status"] == "healthy"
    assert result["parts_count"] == 3
    assert result["documents_count"] == 2
    assert "error" not in result


def test_check_health_sanitizes_internal_error_details(tmp_path: Path) -> None:
    db_path = tmp_path / "broken.sqlite"
    db = Database(db_path, readonly=False)

    result = db.check_health()

    assert result["status"] == "unhealthy"
    assert result["error"] == "database_error"
