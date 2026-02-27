"""
文档改名/移动与 capabilities 接口集成测试
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

_PDF_PAYLOAD = b"%PDF-1.4\n%%EOF\n"


def _make_config(tmp_path: Path, db_path: Path, *, import_mode: str = "auto") -> Config:
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
        import_mode=import_mode,
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


def test_docs_rename_success_updates_db_and_file(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    (cfg.pdf_dir / "dir").mkdir(parents=True, exist_ok=True)
    (cfg.pdf_dir / "dir" / "a.pdf").write_bytes(_PDF_PAYLOAD)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("a.pdf", "dir/a.pdf", "dir/a.pdf", "{}"),
        )
        conn.execute(
            "INSERT INTO scan_state(relative_path, size, mtime, content_hash, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("dir/a.pdf", 1, 1.0, "h"),
        )
        conn.commit()

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(
            port,
            "POST",
            "/api/docs/rename",
            body=json.dumps({"path": "dir/a.pdf", "new_name": "b.pdf"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status == 200
        assert body["updated"] is True
        assert body["old_path"] == "dir/a.pdf"
        assert body["new_path"] == "dir/b.pdf"
        assert not (cfg.pdf_dir / "dir" / "a.pdf").exists()
        assert (cfg.pdf_dir / "dir" / "b.pdf").exists()

        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT pdf_name, relative_path, pdf_path FROM documents WHERE relative_path = ?",
                ("dir/b.pdf",),
            ).fetchone()
            assert row is not None
            assert row[0] == "b.pdf"
            assert row[1] == "dir/b.pdf"
            assert row[2] == "dir/b.pdf"
            assert conn.execute(
                "SELECT COUNT(1) FROM scan_state WHERE relative_path = ?",
                ("dir/b.pdf",),
            ).fetchone()[0] == 1
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_docs_move_success_updates_db_and_file(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    (cfg.pdf_dir / "dir").mkdir(parents=True, exist_ok=True)
    (cfg.pdf_dir / "dir" / "a.pdf").write_bytes(_PDF_PAYLOAD)
    (cfg.pdf_dir / "archive").mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("a.pdf", "dir/a.pdf", "dir/a.pdf", "{}"),
        )
        conn.commit()

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(
            port,
            "POST",
            "/api/docs/move",
            body=json.dumps({"path": "dir/a.pdf", "target_dir": "archive"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status == 200
        assert body["updated"] is True
        assert body["old_path"] == "dir/a.pdf"
        assert body["new_path"] == "archive/a.pdf"
        assert not (cfg.pdf_dir / "dir" / "a.pdf").exists()
        assert (cfg.pdf_dir / "archive" / "a.pdf").exists()

        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT pdf_name, relative_path, pdf_path FROM documents WHERE relative_path = ?",
                ("archive/a.pdf",),
            ).fetchone()
            assert row is not None
            assert row[0] == "a.pdf"
            assert row[1] == "archive/a.pdf"
            assert row[2] == "archive/a.pdf"
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_docs_rename_conflict_returns_409(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    (cfg.pdf_dir / "dir").mkdir(parents=True, exist_ok=True)
    (cfg.pdf_dir / "dir" / "a.pdf").write_bytes(_PDF_PAYLOAD)
    (cfg.pdf_dir / "dir" / "b.pdf").write_bytes(_PDF_PAYLOAD)

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

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(
            port,
            "POST",
            "/api/docs/rename",
            body=json.dumps({"path": "dir/a.pdf", "new_name": "b.pdf"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status == 409
        assert body["error"] == "CONFLICT"
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_docs_move_missing_source_returns_404(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(
            port,
            "POST",
            "/api/docs/move",
            body=json.dumps({"path": "missing.pdf", "target_dir": "archive"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status == 404
        assert body["error"] == "NOT_FOUND"
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_capabilities_reports_enablement_modes(tmp_path: Path) -> None:
    enabled_db = tmp_path / "enabled.sqlite"
    enabled_cfg = _make_config(tmp_path / "enabled", enabled_db, import_mode="auto")
    enabled_server = create_server(enabled_cfg)
    enabled_thread, enabled_port = _start_server(enabled_server)
    try:
        status, body = _request_json(enabled_port, "GET", "/api/capabilities")
        assert status == 200
        assert body["import_enabled"] is True
        assert body["scan_enabled"] is True
        assert body["import_reason"] == ""
        assert body["scan_reason"] == ""
    finally:
        enabled_server.stop()
        enabled_thread.join(timeout=3.0)

    disabled_db = tmp_path / "disabled.sqlite"
    disabled_cfg = _make_config(tmp_path / "disabled", disabled_db, import_mode="disabled")
    disabled_server = create_server(disabled_cfg)
    disabled_thread, disabled_port = _start_server(disabled_server)
    try:
        status, body = _request_json(disabled_port, "GET", "/api/capabilities")
        assert status == 200
        assert body["import_enabled"] is False
        assert body["scan_enabled"] is False
        assert "disabled" in str(body["import_reason"]).lower()
        assert "disabled" in str(body["scan_reason"]).lower()
    finally:
        disabled_server.stop()
        disabled_thread.join(timeout=3.0)
