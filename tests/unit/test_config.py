"""
配置模块单元测试
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from ipc_query.config import Config
from ipc_query.exceptions import ConfigurationError


def test_database_path_has_priority_over_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", "/tmp/primary.sqlite")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/fallback.sqlite")

    config = Config.from_env()
    assert config.database_path == Path("/tmp/primary.sqlite")


def test_database_url_sqlite_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/from-url.sqlite")

    config = Config.from_env()
    assert config.database_path == Path("/tmp/from-url.sqlite")


def test_database_url_sqlite_relative_path_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:./tmp/relative.sqlite")

    config = Config.from_env()
    assert config.database_path == Path("./tmp/relative.sqlite")


def test_invalid_database_url_scheme_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")

    with pytest.raises(ConfigurationError):
        Config.from_env()


def test_upload_dir_defaults_to_pdf_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UPLOAD_DIR", raising=False)
    monkeypatch.setenv("PDF_DIR", "/tmp/ipc-pdfs")

    config = Config.from_env()
    assert config.pdf_dir == Path("/tmp/ipc-pdfs")
    assert config.upload_dir == Path("/tmp/ipc-pdfs")


def test_import_jobs_retained_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMPORT_JOBS_RETAINED", "321")

    config = Config.from_env()
    assert config.import_jobs_retained == 321


def test_from_args_pdf_dir_defaults_upload_dir_to_same_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDF_DIR", raising=False)
    monkeypatch.delenv("UPLOAD_DIR", raising=False)
    args = Namespace(
        db=None,
        host=None,
        port=None,
        pdf_dir="/tmp/cli-pdfs",
        upload_dir=None,
        static_dir=None,
        debug=False,
    )

    config = Config.from_args(args)
    assert config.pdf_dir == Path("/tmp/cli-pdfs")
    assert config.upload_dir == Path("/tmp/cli-pdfs")
