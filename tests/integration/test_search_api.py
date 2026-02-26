"""
GET /api/search 接口集成测试
"""

from __future__ import annotations

import http.client
import json
import threading
import time
from pathlib import Path

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


def _request_json(port: int, path: str) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        conn.request("GET", path, headers={"Accept": "application/json"})
        resp = conn.getresponse()
        payload = resp.read()
    finally:
        conn.close()

    return resp.status, json.loads(payload.decode("utf-8"))


def test_search_api_response_contains_match_and_page_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(port, "/api/search?q=ABC&match=pn&page=0&page_size=10")

        assert status == 200
        assert body["match"] == "pn"
        assert body["page"] == 1
        assert body["page_size"] == 10
        assert body["has_more"] is False
        assert isinstance(body["results"], list)
    finally:
        server.stop()
        thread.join(timeout=3.0)
