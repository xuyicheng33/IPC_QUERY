"""
v4.0 稳定性与安全加固集成测试
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

_PDF_PAYLOAD = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _make_config(
    tmp_path: Path,
    db_path: Path,
    *,
    import_mode: str = "auto",
    write_api_auth_mode: str = "disabled",
    write_api_key: str = "",
    legacy_folder_routes_enabled: bool = True,
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
        import_mode=import_mode,
        write_api_auth_mode=write_api_auth_mode,
        write_api_key=write_api_key,
        legacy_folder_routes_enabled=legacy_folder_routes_enabled,
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
) -> tuple[int, dict, dict[str, str]]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)
        conn.request(method, path, body=body, headers=req_headers)
        resp = conn.getresponse()
        payload = resp.read()
        out_headers = {k.lower(): v for (k, v) in resp.getheaders()}
    finally:
        conn.close()

    data = json.loads(payload.decode("utf-8")) if payload else {}
    return resp.status, data, out_headers


def test_write_api_key_auth_enforced_for_write_routes(tmp_path: Path) -> None:
    db_path = tmp_path / "data.sqlite"
    cfg = _make_config(
        tmp_path,
        db_path,
        write_api_auth_mode="api_key",
        write_api_key="secret-key",
    )
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status_health, _body_health, _ = _request(port, "GET", "/api/health")
        assert status_health == 200

        status_missing, body_missing, _ = _request(
            port,
            "POST",
            "/api/folders",
            body=json.dumps({"path": "", "name": "engine"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status_missing == 401
        assert body_missing["error"] == "UNAUTHORIZED"

        status_wrong, body_wrong, _ = _request(
            port,
            "POST",
            "/api/folders",
            body=json.dumps({"path": "", "name": "engine"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-API-Key": "wrong"},
        )
        assert status_wrong == 401
        assert body_wrong["error"] == "UNAUTHORIZED"

        status_ok, body_ok, _ = _request(
            port,
            "POST",
            "/api/folders",
            body=json.dumps({"path": "", "name": "engine"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-API-Key": "secret-key"},
        )
        assert status_ok == 201
        assert body_ok["created"] is True

        status_del_missing, body_del_missing, _ = _request(port, "DELETE", "/api/docs?name=missing.pdf")
        assert status_del_missing == 401
        assert body_del_missing["error"] == "UNAUTHORIZED"

        status_del_with_key, body_del_with_key, _ = _request(
            port,
            "DELETE",
            "/api/docs?name=missing.pdf",
            headers={"X-API-Key": "secret-key"},
        )
        assert status_del_with_key == 404
        assert body_del_with_key["error"] == "NOT_FOUND"
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_legacy_folder_routes_work_and_return_deprecation_headers(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.sqlite"
    cfg = _make_config(tmp_path, db_path, legacy_folder_routes_enabled=True)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status_new, body_new, headers_new = _request(
            port,
            "POST",
            "/api/folders",
            body=json.dumps({"path": "", "name": "canonical"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status_new == 201
        assert body_new["created"] is True
        assert "deprecation" not in headers_new

        status_old, body_old, headers_old = _request(
            port,
            "POST",
            "/api/docs/folder/create",
            body=json.dumps({"path": "", "name": "legacy"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status_old == 201
        assert body_old["created"] is True
        assert headers_old.get("deprecation") == "true"
        assert headers_old.get("sunset") == "2026-06-30"
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_legacy_folder_routes_can_be_disabled(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-off.sqlite"
    cfg = _make_config(tmp_path, db_path, legacy_folder_routes_enabled=False)
    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status_old, body_old, _ = _request(
            port,
            "POST",
            "/api/docs/folder/create",
            body=json.dumps({"path": "", "name": "legacy"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status_old == 404
        assert body_old["error"] == "NOT_FOUND"

        status_new, body_new, _ = _request(
            port,
            "POST",
            "/api/folders",
            body=json.dumps({"path": "", "name": "canonical"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status_new == 201
        assert body_new["created"] is True
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_single_level_directory_policy_rejects_nested_paths(tmp_path: Path) -> None:
    db_path = tmp_path / "single-level.sqlite"
    cfg = _make_config(tmp_path, db_path)
    (cfg.pdf_dir / "a.pdf").write_bytes(_PDF_PAYLOAD)
    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("a.pdf", "a.pdf", "a.pdf", "{}"),
        )
        conn.commit()

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status_upload, body_upload, _ = _request(
            port,
            "POST",
            f"/api/import?filename=part.pdf&target_dir={quote('x/y', safe='')}",
            body=_PDF_PAYLOAD,
            headers={
                "Content-Type": "application/pdf",
                "X-File-Name": "part.pdf",
                "X-Target-Dir": "x/y",
            },
        )
        assert status_upload == 400
        assert body_upload["error"] == "VALIDATION_ERROR"

        status_move, body_move, _ = _request(
            port,
            "POST",
            "/api/docs/move",
            body=json.dumps({"path": "a.pdf", "target_dir": "x/y"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert status_move == 400
        assert body_move["error"] == "VALIDATION_ERROR"

        status_scan, body_scan, _ = _request(port, "POST", "/api/scan?path=x/y")
        assert status_scan == 400
        assert body_scan["error"] == "VALIDATION_ERROR"

        status_tree, body_tree, _ = _request(port, "GET", "/api/docs/tree?path=x/y")
        assert status_tree == 400
        assert body_tree["error"] == "VALIDATION_ERROR"
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_capabilities_include_v4_fields_and_deep_path_warning_count(tmp_path: Path) -> None:
    db_path = tmp_path / "warning.sqlite"
    cfg = _make_config(
        tmp_path,
        db_path,
        write_api_auth_mode="api_key",
        write_api_key="secret-key",
        legacy_folder_routes_enabled=True,
    )
    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("deep.pdf", "a/b/deep.pdf", "a/b/deep.pdf", "{}"),
        )
        conn.commit()

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status, body, _ = _request(port, "GET", "/api/capabilities")
        assert status == 200
        assert body["write_auth_mode"] == "api_key"
        assert body["write_auth_required"] is True
        assert body["legacy_folder_routes_enabled"] is True
        assert body["directory_policy"] == "single_level"
        assert int(body["path_policy_warning_count"]) == 1
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_docs_and_docs_tree_do_not_expose_internal_paths(tmp_path: Path) -> None:
    db_path = tmp_path / "docs-security.sqlite"
    cfg = _make_config(tmp_path, db_path)
    (cfg.pdf_dir / "a.pdf").write_bytes(_PDF_PAYLOAD)
    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("a.pdf", "a.pdf", "/abs/path/a.pdf", "/abs/miner/a"),
        )
        conn.commit()

    server = create_server(cfg)
    thread, port = _start_server(server)
    try:
        status_docs, body_docs, _ = _request(port, "GET", "/api/docs")
        assert status_docs == 200
        assert isinstance(body_docs, list)
        assert body_docs[0]["relative_path"] == "a.pdf"
        assert "pdf_path" not in body_docs[0]
        assert "miner_dir" not in body_docs[0]

        status_tree, body_tree, _ = _request(port, "GET", "/api/docs/tree?path=")
        assert status_tree == 200
        row = next(item for item in body_tree["files"] if item["name"] == "a.pdf")
        assert row["indexed"] is True
        assert "pdf_path" not in row["document"]
        assert "miner_dir" not in row["document"]
    finally:
        server.stop()
        thread.join(timeout=3.0)
