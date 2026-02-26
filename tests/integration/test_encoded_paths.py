"""
URL 编码路径集成测试
"""

from __future__ import annotations

import http.client
import threading
import time
from pathlib import Path
from urllib.parse import quote

import fitz

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


def _request(port: int, method: str, path: str) -> tuple[int, bytes, str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        conn.request(method, path)
        resp = conn.getresponse()
        payload = resp.read()
        content_type = str(resp.getheader("Content-Type") or "")
    finally:
        conn.close()

    return resp.status, payload, content_type


def test_pdf_endpoint_supports_url_encoded_name(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)

    pdf_name = "a b.pdf"
    pdf_path = cfg.pdf_dir / pdf_name
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body, content_type = _request(port, "GET", f"/pdf/{quote(pdf_name, safe='')}")
        assert status == 200
        assert content_type == "application/pdf"
        assert body.startswith(b"%PDF-")
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_render_endpoint_supports_url_encoded_name(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)

    pdf_name = "a b.pdf"
    pdf_path = cfg.pdf_dir / pdf_name
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello")
    doc.save(str(pdf_path))
    doc.close()

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body, content_type = _request(port, "GET", f"/render/{quote(pdf_name, safe='')}/1.png")
        assert status == 200
        assert content_type == "image/png"
        assert body.startswith(b"\x89PNG\r\n\x1a\n")
    finally:
        server.stop()
        thread.join(timeout=3.0)
