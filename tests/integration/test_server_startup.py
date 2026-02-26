"""
服务器启动链路测试
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from build_db import ensure_schema
from ipc_query.api.server import create_server
from ipc_query.config import Config


def _make_config(tmp_path: Path, db_path: Path) -> Config:
    pdf_dir = tmp_path / "pdfs"
    cache_dir = tmp_path / "cache"
    cfg = Config(
        database_path=db_path,
        static_dir=Path("web"),
        pdf_dir=pdf_dir,
        upload_dir=pdf_dir,
        cache_dir=cache_dir,
    )
    cfg.ensure_directories()
    return cfg


def test_create_server_with_readonly_db_does_not_write(tmp_path: Path) -> None:
    db_path = tmp_path / "readonly.sqlite"
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_schema(conn)
    finally:
        conn.close()

    db_path.chmod(0o444)
    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    try:
        assert server is not None
    finally:
        server.stop()
        db_path.chmod(0o644)


def test_create_server_can_bootstrap_missing_db(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.sqlite"
    assert not db_path.exists()

    cfg = _make_config(tmp_path, db_path)
    server = create_server(cfg)
    try:
        assert db_path.exists()
    finally:
        server.stop()
