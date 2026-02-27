"""
POST /api/docs/batch-delete 集成测试
"""

from __future__ import annotations

import http.client
import json
import sqlite3
import threading
import time
from pathlib import Path

from build_db import ensure_schema
from ipc_query.api.server import create_server
from ipc_query.config import Config
from ipc_query.services import scanner as scanner_module


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


def _request_json(
    port: int,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)
        conn.request(method, path, body=body, headers=req_headers)
        resp = conn.getresponse()
        payload = resp.read()
    finally:
        conn.close()

    data = json.loads(payload.decode("utf-8")) if payload else {}
    return resp.status, data


def _insert_doc(conn: sqlite3.Connection, pdf_name: str, relative_path: str) -> None:
    conn.execute(
        """
        INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        """,
        (pdf_name, relative_path, relative_path, "{}"),
    )


def test_batch_delete_all_success(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    monkeypatch.setattr(scanner_module, "ingest_pdfs", lambda *_args, **_kwargs: {"docs_ingested": 0, "docs_replaced": 0, "parts_ingested": 0, "xrefs_ingested": 0, "aliases_ingested": 0})

    (cfg.pdf_dir / "sub").mkdir(parents=True, exist_ok=True)
    (cfg.pdf_dir / "a.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (cfg.pdf_dir / "sub" / "b.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        _insert_doc(conn, "a.pdf", "a.pdf")
        _insert_doc(conn, "b.pdf", "sub/b.pdf")
        conn.commit()

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(
            port,
            "POST",
            "/api/docs/batch-delete",
            body=json.dumps({"paths": ["a.pdf", "sub/b.pdf"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        assert status == 200
        assert body["total"] == 2
        assert body["deleted"] == 2
        assert body["failed"] == 0
        assert [item["path"] for item in body["results"]] == ["a.pdf", "sub/b.pdf"]
        assert all(item["ok"] is True for item in body["results"])
        assert not (cfg.pdf_dir / "a.pdf").exists()
        assert not (cfg.pdf_dir / "sub" / "b.pdf").exists()

        with sqlite3.connect(str(db_path)) as conn:
            remaining = conn.execute("SELECT COUNT(1) FROM documents").fetchone()[0]
            assert remaining == 0
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_batch_delete_partial_failure_with_relative_path(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    monkeypatch.setattr(scanner_module, "ingest_pdfs", lambda *_args, **_kwargs: {"docs_ingested": 0, "docs_replaced": 0, "parts_ingested": 0, "xrefs_ingested": 0, "aliases_ingested": 0})

    (cfg.pdf_dir / "sub").mkdir(parents=True, exist_ok=True)
    existing = cfg.pdf_dir / "sub" / "a b.pdf"
    existing.write_bytes(b"%PDF-1.4\n%%EOF\n")

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        _insert_doc(conn, "a b.pdf", "sub/a b.pdf")
        conn.commit()

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(
            port,
            "POST",
            "/api/docs/batch-delete",
            body=json.dumps({"paths": ["sub/a b.pdf", "sub/missing.pdf"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        assert status == 200
        assert body["total"] == 2
        assert body["deleted"] == 1
        assert body["failed"] == 1
        assert body["results"][0]["path"] == "sub/a b.pdf"
        assert body["results"][0]["ok"] is True
        assert body["results"][1]["path"] == "sub/missing.pdf"
        assert body["results"][1]["ok"] is False
        assert "not found" in body["results"][1]["error"].lower()
        assert not existing.exists()

        with sqlite3.connect(str(db_path)) as conn:
            remaining = conn.execute("SELECT COUNT(1) FROM documents").fetchone()[0]
            assert remaining == 0
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_batch_delete_reports_conflict_details(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    monkeypatch.setattr(
        scanner_module,
        "ingest_pdfs",
        lambda *_args, **_kwargs: {
            "docs_ingested": 0,
            "docs_replaced": 0,
            "parts_ingested": 0,
            "xrefs_ingested": 0,
            "aliases_ingested": 0,
        },
    )

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
        status, body = _request_json(
            port,
            "POST",
            "/api/docs/batch-delete",
            body=json.dumps({"paths": ["same.pdf"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status == 200
        assert body["failed"] == 1
        item = body["results"][0]
        assert item["ok"] is False
        assert item["error_code"] == "CONFLICT"
        assert item["details"]["candidates"] == ["dir1/same.pdf", "dir2/same.pdf"]
    finally:
        server.stop()
        thread.join(timeout=3.0)
