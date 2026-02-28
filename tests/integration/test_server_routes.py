"""
服务器路由与错误分支集成测试
"""

from __future__ import annotations

import http.client
import json
import threading
import time
from pathlib import Path
from urllib.parse import quote

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


def _request(
    port: int,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        req_headers = headers or {}
        conn.request(method, path, body=body, headers=req_headers)
        resp = conn.getresponse()
        payload = resp.read()
        out_headers = {k.lower(): v for (k, v) in resp.getheaders()}
    finally:
        conn.close()
    return resp.status, payload, out_headers


def test_head_root_and_static_not_found(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, _payload, headers = _request(port, "HEAD", "/")
        assert status == 200
        assert "content-length" in headers

        status_404, payload_404, _headers_404 = _request(port, "GET", "/not-found.js")
        assert status_404 == 404
        body = json.loads(payload_404.decode("utf-8"))
        assert body["error"] == "not_found"
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_web_route_aliases_return_html(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        for path in ("/search", "/db", "/part/1"):
            status, payload, headers = _request(port, "GET", path)
            assert status == 200
            assert "text/html" in headers.get("content-type", "")
            assert b"<!doctype html>" in payload.lower()
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_legacy_viewer_page_is_removed(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, payload, _ = _request(port, "GET", "/viewer.html")
        assert status == 404
        body = json.loads(payload.decode("utf-8"))
        assert body["error"] == "not_found"
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_post_and_delete_unsupported_paths_return_not_found(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status_post, payload_post, _ = _request(port, "POST", "/api/unknown")
        body_post = json.loads(payload_post.decode("utf-8"))
        assert status_post == 404
        assert body_post["error"] == "NOT_FOUND"

        status_del, payload_del, _ = _request(port, "DELETE", "/api/unknown")
        body_del = json.loads(payload_del.decode("utf-8"))
        assert status_del == 404
        assert body_del["error"] == "NOT_FOUND"
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_import_job_not_found_and_missing_id(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status_missing, payload_missing, _ = _request(port, "GET", "/api/import/not-exists")
        body_missing = json.loads(payload_missing.decode("utf-8"))
        assert status_missing == 404
        assert body_missing["error"] == "NOT_FOUND"

        status_no_id, payload_no_id, _ = _request(port, "GET", "/api/import/")
        body_no_id = json.loads(payload_no_id.decode("utf-8"))
        assert status_no_id == 404
        assert body_no_id["error"] == "NOT_FOUND"
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_pdf_range_request_returns_partial_content(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)

    pdf_name = "range test.pdf"
    pdf_path = cfg.pdf_dir / pdf_name
    content = b"%PDF-1.4\nabcdefg\n%%EOF\n"
    pdf_path.write_bytes(content)

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, payload, headers = _request(
            port,
            "GET",
            f"/pdf/{quote(pdf_name, safe='')}",
            headers={"Range": "bytes=0-4"},
        )
        assert status == 206
        assert payload == content[:5]
        assert headers.get("content-range", "").startswith("bytes 0-4/")
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_render_invalid_path_returns_not_found(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, payload, _ = _request(port, "GET", "/render/not-a-valid-path")
        body = json.loads(payload.decode("utf-8"))
        assert status == 404
        assert body["error"] == "NOT_FOUND"
    finally:
        server.stop()
        thread.join(timeout=3.0)
