"""
/api/import 相关接口集成测试
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
from ipc_query.services import importer as importer_module

_PDF_PAYLOAD = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _make_config(
    tmp_path: Path,
    db_path: Path,
    *,
    max_file_size_mb: int = 100,
    import_mode: str = "auto",
) -> Config:
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
        import_max_file_size_mb=max_file_size_mb,
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


def _raw_post_json(port: int, path: str, headers: dict[str, str], body: bytes = b"") -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        conn.putrequest("POST", path)
        for k, v in headers.items():
            conn.putheader(k, v)
        conn.endheaders()
        if body:
            conn.send(body)
        resp = conn.getresponse()
        payload = resp.read()
    finally:
        conn.close()

    data = json.loads(payload.decode("utf-8")) if payload else {}
    return resp.status, data


def _wait_for_job(port: int, job_id: str, timeout_s: float = 3.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status, body = _request_json(port, "GET", f"/api/import/{job_id}")
        assert status == 200
        if body.get("status") in {"success", "failed"}:
            return body
        time.sleep(0.02)
    raise AssertionError("import job did not reach terminal state in time")


def test_import_submit_and_jobs_endpoints(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path, import_mode="enabled")

    def _fake_ingest(_conn: object, _pdf_paths: list[Path]) -> dict[str, int]:
        return {
            "docs_ingested": 1,
            "docs_replaced": 0,
            "parts_ingested": 0,
            "xrefs_ingested": 0,
            "aliases_ingested": 0,
        }

    monkeypatch.setattr(importer_module, "ingest_pdfs", _fake_ingest)

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(
            port,
            "POST",
            "/api/import",
            body=_PDF_PAYLOAD,
            headers={
                "Content-Type": "application/pdf",
                "X-File-Name": "uploaded.pdf",
            },
        )
        assert status == 202
        job_id = str(body.get("job_id") or "")
        assert job_id

        terminal = _wait_for_job(port, job_id)
        assert terminal["status"] == "success"
        assert terminal["summary"]["docs_ingested"] == 1

        status_jobs, jobs_body = _request_json(port, "GET", "/api/import/jobs?limit=10")
        assert status_jobs == 200
        job_ids = [str(item["job_id"]) for item in jobs_body["jobs"]]
        assert job_id in job_ids
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_import_rejects_missing_content_length(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _raw_post_json(
            port,
            "/api/import?filename=no-length.pdf",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/pdf",
                "X-File-Name": "no-length.pdf",
            },
        )
        assert status == 400
        assert body["error"] == "VALIDATION_ERROR"
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_import_rejects_invalid_content_length(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _raw_post_json(
            port,
            "/api/import?filename=bad-length.pdf",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/pdf",
                "X-File-Name": "bad-length.pdf",
                "Content-Length": "abc",
            },
        )
        assert status == 400
        assert body["error"] == "VALIDATION_ERROR"
        assert "Content-Length" in body["message"]
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_import_rejects_oversized_body(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path, max_file_size_mb=1)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _raw_post_json(
            port,
            "/api/import",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/pdf",
                "X-File-Name": "too-large.pdf",
                "Content-Length": str(2 * 1024 * 1024),
            },
        )
        assert status == 400
        assert body["error"] == "VALIDATION_ERROR"
        assert "File too large" in body["message"]
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_import_rejects_invalid_pdf_signature(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(
            port,
            "POST",
            "/api/import",
            body=b"not a pdf",
            headers={
                "Content-Type": "application/pdf",
                "X-File-Name": "bad.pdf",
            },
        )
        assert status == 400
        assert body["error"] == "VALIDATION_ERROR"
        assert "signature" in body["message"].lower()
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_import_disabled_when_db_is_readonly(tmp_path: Path) -> None:
    db_path = tmp_path / "readonly.sqlite"
    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)

    db_path.chmod(0o444)
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(
            port,
            "POST",
            "/api/import",
            body=_PDF_PAYLOAD,
            headers={
                "Content-Type": "application/pdf",
                "X-File-Name": "readonly.pdf",
            },
        )
        assert status == 400
        assert body["error"] == "VALIDATION_ERROR"
        assert "not enabled" in body["message"].lower()
    finally:
        server.stop()
        thread.join(timeout=3.0)
        db_path.chmod(0o644)


def test_import_disabled_when_import_mode_is_disabled(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(tmp_path, db_path, import_mode="disabled")
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body = _request_json(
            port,
            "POST",
            "/api/import",
            body=_PDF_PAYLOAD,
            headers={
                "Content-Type": "application/pdf",
                "X-File-Name": "disabled.pdf",
            },
        )
        assert status == 400
        assert body["error"] == "VALIDATION_ERROR"
        assert "not enabled" in body["message"].lower()
    finally:
        server.stop()
        thread.join(timeout=3.0)
