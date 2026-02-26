"""
数据库管理接口集成测试（目录树/文件夹/扫描）
"""

from __future__ import annotations

import http.client
import json
import threading
import time
from pathlib import Path

from ipc_query.api.server import create_server
from ipc_query.config import Config
from ipc_query.services import importer as importer_module
from ipc_query.services import scanner as scanner_module

_PDF_PAYLOAD = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


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


def _wait_job(port: int, path: str, timeout_s: float = 4.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status, body = _request_json(port, "GET", path)
        assert status == 200
        if body.get("status") in {"success", "failed"}:
            return body
        time.sleep(0.03)
    raise AssertionError("job did not finish")


def test_folders_tree_import_and_scan(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)

    def _fake_ingest(_conn: object, _pdf_paths: list[Path], **_kwargs: object) -> dict[str, int]:
        return {
            "docs_ingested": 1,
            "docs_replaced": 0,
            "parts_ingested": 0,
            "xrefs_ingested": 0,
            "aliases_ingested": 0,
        }

    monkeypatch.setattr(importer_module, "ingest_pdfs", _fake_ingest)
    monkeypatch.setattr(scanner_module, "ingest_pdfs", _fake_ingest)

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status_folder, _ = _request_json(
            port,
            "POST",
            "/api/folders",
            body=json.dumps({"path": "", "name": "engine"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status_folder == 201
        assert (cfg.pdf_dir / "engine").is_dir()

        status_import, import_job = _request_json(
            port,
            "POST",
            "/api/import?filename=part.pdf&target_dir=engine",
            body=_PDF_PAYLOAD,
            headers={
                "Content-Type": "application/pdf",
                "X-File-Name": "part.pdf",
                "X-Target-Dir": "engine",
            },
        )
        assert status_import == 202
        import_terminal = _wait_job(port, f"/api/import/{import_job['job_id']}")
        assert import_terminal["status"] == "success"
        assert (cfg.pdf_dir / "engine" / "part.pdf").exists()

        status_tree, tree = _request_json(port, "GET", "/api/docs/tree?path=engine")
        assert status_tree == 200
        assert any(f["name"] == "part.pdf" for f in tree["files"])

        # 新文件写入后触发手动扫描
        (cfg.pdf_dir / "engine" / "late.pdf").write_bytes(_PDF_PAYLOAD)
        status_scan, scan_job = _request_json(port, "POST", "/api/scan?path=engine")
        assert status_scan == 202
        scan_terminal = _wait_job(port, f"/api/scan/{scan_job['job_id']}")
        assert scan_terminal["status"] == "success"
        assert int(scan_terminal["summary"]["scanned_files"]) >= 1
    finally:
        server.stop()
        thread.join(timeout=3.0)
