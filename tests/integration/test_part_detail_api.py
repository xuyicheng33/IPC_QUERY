"""
GET /api/part/{id} 集成测试
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


def test_part_detail_includes_source_relative_path(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)

    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        cur = conn.execute(
            """
            INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            ("a.pdf", "sub/a.pdf", "sub/a.pdf", "{}"),
        )
        doc_id = int(cur.lastrowid)
        cur = conn.execute(
            """
            INSERT INTO parts(
              document_id, page_num, page_end, extractor, row_kind,
              part_number_cell, part_number_canonical, nom_level, nomenclature, nomenclature_clean
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, 1, 1, "pdf_coords", "part", "P-1", "P-1", 0, "DESC", "DESC"),
        )
        part_id = int(cur.lastrowid)
        conn.commit()

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(port, "GET", f"/api/part/{part_id}")
        assert status == 200
        assert body["part"]["pdf"] == "a.pdf"
        assert body["part"]["source_relative_path"] == "sub/a.pdf"
    finally:
        server.stop()
        thread.join(timeout=3.0)
