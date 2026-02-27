"""
DELETE /api/docs 接口集成测试
"""

from __future__ import annotations

import http.client
import json
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import quote

from build_db import ensure_schema
from ipc_query.api.server import create_server
from ipc_query.config import Config


def _make_config(tmp_path: Path, db_path: Path) -> Config:
    pdf_dir = tmp_path / "pdfs"
    cache_dir = tmp_path / "cache"
    cfg = Config(
        database_path=db_path,
        host="127.0.0.1",
        port=0,
        static_dir=Path("web"),
        pdf_dir=pdf_dir,
        upload_dir=pdf_dir,
        cache_dir=cache_dir,
    )
    cfg.ensure_directories()
    return cfg


def _start_server(server) -> tuple[threading.Thread, int]:
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()

    deadline = time.time() + 5.0
    while time.time() < deadline:
        if server._server is not None:
            return thread, int(server._server.server_address[1])
        time.sleep(0.02)

    server.stop()
    thread.join(timeout=2.0)
    raise AssertionError("server did not start in time")


def _request_json(port: int, method: str, path: str) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        conn.request(method, path, headers={"Accept": "application/json"})
        resp = conn.getresponse()
        payload = resp.read()
    finally:
        conn.close()

    data = json.loads(payload.decode("utf-8")) if payload else {}
    return resp.status, data


def test_delete_doc_via_query_path_removes_document_and_pdf(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, datetime('now'))",
            ("to-delete.pdf", "to-delete.pdf", "{}",),
        )
        conn.commit()

    pdf_path = cfg.pdf_dir / "to-delete.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(port, "DELETE", "/api/docs?name=to-delete.pdf")
        assert status == 200
        assert body["deleted"] is True
        assert body["pdf_name"] == "to-delete.pdf"
        assert body["file_deleted"] is True
        assert not pdf_path.exists()

        with sqlite3.connect(str(db_path)) as conn:
            assert conn.execute("SELECT COUNT(1) FROM documents").fetchone()[0] == 0
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_delete_doc_via_rest_path_returns_404_when_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        missing_name = "missing name.pdf"
        encoded_name = quote(missing_name, safe="")
        status, body = _request_json(port, "DELETE", f"/api/docs/{encoded_name}")

        assert status == 404
        assert body["error"] == "NOT_FOUND"
        assert missing_name in body["message"]
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_delete_doc_returns_409_for_ambiguous_basename(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)

    with sqlite3.connect(str(db_path)) as conn:
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

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(port, "DELETE", "/api/docs?name=same.pdf")
        assert status == 409
        assert body["error"] == "CONFLICT"
        assert body["details"]["candidates"] == ["dir1/same.pdf", "dir2/same.pdf"]
    finally:
        server.stop()
        thread.join(timeout=3.0)
