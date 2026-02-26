"""
配置模块单元测试
"""

from __future__ import annotations

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


def test_invalid_database_url_scheme_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")

    with pytest.raises(ConfigurationError):
        Config.from_env()
