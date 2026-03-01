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


def test_import_queue_size_defaults_to_64(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IMPORT_QUEUE_SIZE", raising=False)

    config = Config.from_env()
    assert config.import_queue_size == 64


def test_import_mode_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMPORT_MODE", "enabled")
    config = Config.from_env()
    assert config.import_mode == "enabled"


def test_import_mode_invalid_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMPORT_MODE", "always-on")
    with pytest.raises(ConfigurationError):
        Config.from_env()


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


def test_write_api_auth_mode_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRITE_API_AUTH_MODE", "api_key")
    monkeypatch.delenv("WRITE_API_KEY", raising=False)

    with pytest.raises(ConfigurationError):
        Config.from_env()


def test_write_api_auth_mode_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRITE_API_AUTH_MODE", "api_key")
    monkeypatch.setenv("WRITE_API_KEY", "secret")

    config = Config.from_env()
    assert config.write_api_auth_mode == "api_key"
    assert config.write_api_key == "secret"


def test_legacy_folder_routes_enabled_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEGACY_FOLDER_ROUTES_ENABLED", "false")

    config = Config.from_env()
    assert config.legacy_folder_routes_enabled is False


def test_render_workers_env_acts_as_render_semaphore_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER_WORKERS", "7")
    monkeypatch.delenv("RENDER_SEMAPHORE", raising=False)

    config = Config.from_env()
    assert config.render_semaphore == 7
    assert config.render_workers == 7


def test_render_semaphore_takes_precedence_over_render_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER_WORKERS", "7")
    monkeypatch.setenv("RENDER_SEMAPHORE", "3")

    config = Config.from_env()
    assert config.render_semaphore == 3
    assert config.render_workers == 3
