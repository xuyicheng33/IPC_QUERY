from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

import ipc_query.build_db as build_db_module


class _FailingConn:
    def __init__(self, raw: sqlite3.Connection):
        self._raw = raw
        self._doc_insert_count = 0

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        normalized = " ".join(sql.strip().split()).upper()
        if normalized.startswith("INSERT INTO DOCUMENTS"):
            self._doc_insert_count += 1
            if self._doc_insert_count >= 2:
                raise sqlite3.OperationalError("injected document insert failure")
        return self._raw.execute(sql, params)

    def executescript(self, script: str) -> sqlite3.Cursor:
        return self._raw.executescript(script)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def __getattr__(self, item: str) -> Any:
        return getattr(self._raw, item)


def test_ingest_pdfs_rolls_back_when_midway_failure_occurs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_build_db(output_path: Path, pdf_paths: list[Path], base_dir: Path | None = None) -> None:
        with sqlite3.connect(str(output_path)) as conn:
            build_db_module.ensure_schema(conn)
            conn.execute(
                "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
                ("doc-1.pdf", "dir/doc-1.pdf", "dir/doc-1.pdf", "{}"),
            )
            conn.execute(
                "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
                ("doc-2.pdf", "dir/doc-2.pdf", "dir/doc-2.pdf", "{}"),
            )
            conn.commit()

    monkeypatch.setattr(build_db_module, "build_db", _fake_build_db)

    db_path = tmp_path / "target.sqlite"
    raw_conn = sqlite3.connect(str(db_path))
    try:
        build_db_module.ensure_schema(raw_conn)
        raw_conn.execute(
            "INSERT INTO documents(pdf_name, relative_path, pdf_path, miner_dir, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("keep.pdf", "keep.pdf", "keep.pdf", "{}"),
        )
        raw_conn.commit()

        failing_conn = _FailingConn(raw_conn)
        with pytest.raises(sqlite3.OperationalError):
            build_db_module.ingest_pdfs(
                failing_conn,  # type: ignore[arg-type]
                [Path("a.pdf"), Path("b.pdf")],
            )

        rows = raw_conn.execute(
            "SELECT pdf_name, relative_path FROM documents ORDER BY id"
        ).fetchall()
        assert rows == [("keep.pdf", "keep.pdf")]
    finally:
        raw_conn.close()
