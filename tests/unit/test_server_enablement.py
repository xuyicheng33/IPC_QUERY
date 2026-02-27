"""
Import/scan enablement 决策测试
"""

from __future__ import annotations

from pathlib import Path

from ipc_query.api import server as server_module
from ipc_query.config import Config


def _make_config(tmp_path: Path, *, import_mode: str) -> Config:
    pdf_dir = tmp_path / "pdfs"
    upload_dir = tmp_path / "uploads"
    cache_dir = tmp_path / "cache"
    cfg = Config(
        database_path=tmp_path / "ipc.sqlite",
        static_dir=Path("web"),
        pdf_dir=pdf_dir,
        upload_dir=upload_dir,
        cache_dir=cache_dir,
        import_mode=import_mode,
    )
    cfg.ensure_directories()
    return cfg


def test_resolve_import_enablement_disabled(monkeypatch, tmp_path: Path) -> None:
    cfg = _make_config(tmp_path, import_mode="disabled")

    monkeypatch.setattr(
        server_module,
        "_is_database_writable",
        lambda _path: (_ for _ in ()).throw(AssertionError("should not probe db when disabled")),
    )
    monkeypatch.setattr(
        server_module,
        "_is_directory_writable",
        lambda _path: (_ for _ in ()).throw(AssertionError("should not probe fs when disabled")),
    )

    enabled, details = server_module._resolve_import_enablement(cfg)

    assert enabled is False
    assert details["mode"] == "disabled"
    assert details["reason"] == "disabled_by_config"


def test_resolve_import_enablement_enabled_success(monkeypatch, tmp_path: Path) -> None:
    cfg = _make_config(tmp_path, import_mode="enabled")

    monkeypatch.setattr(server_module, "_is_database_writable", lambda _path: True)
    monkeypatch.setattr(server_module, "_is_directory_writable", lambda _path: True)

    enabled, details = server_module._resolve_import_enablement(cfg)

    assert enabled is True
    assert details["mode"] == "enabled"
    assert details["db_writable"] is True
    assert details["pdf_writable"] is True
    assert details["upload_writable"] is True
    assert "reason" not in details


def test_resolve_import_enablement_enabled_degrades_when_not_writable(
    monkeypatch, tmp_path: Path
) -> None:
    cfg = _make_config(tmp_path, import_mode="enabled")

    monkeypatch.setattr(server_module, "_is_database_writable", lambda _path: True)
    monkeypatch.setattr(
        server_module,
        "_is_directory_writable",
        lambda path: path != cfg.pdf_dir,
    )

    enabled, details = server_module._resolve_import_enablement(cfg)

    assert enabled is False
    assert details["mode"] == "enabled"
    assert details["db_writable"] is True
    assert details["pdf_writable"] is False
    assert details["upload_writable"] is True
    assert details["reason"] == "enabled_but_write_requirements_not_met"


def test_resolve_import_enablement_auto_disables_when_requirements_fail(
    monkeypatch, tmp_path: Path
) -> None:
    cfg = _make_config(tmp_path, import_mode="auto")

    monkeypatch.setattr(server_module, "_is_database_writable", lambda _path: False)
    monkeypatch.setattr(server_module, "_is_directory_writable", lambda _path: True)

    enabled, details = server_module._resolve_import_enablement(cfg)

    assert enabled is False
    assert details["mode"] == "auto"
    assert details["db_writable"] is False
    assert details["pdf_writable"] is True
    assert details["upload_writable"] is True
    assert details["reason"] == "auto_disabled_due_to_write_requirements"
