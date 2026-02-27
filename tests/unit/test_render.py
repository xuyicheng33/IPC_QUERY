from __future__ import annotations

from pathlib import Path

import fitz

from ipc_query.config import Config
from ipc_query.services.render import create_render_service


def _create_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()


def _make_service(tmp_path: Path):
    pdf_dir = tmp_path / "pdfs"
    cache_dir = tmp_path / "cache"
    cfg = Config(pdf_dir=pdf_dir, cache_dir=cache_dir)
    cfg.ensure_directories()
    return create_render_service(pdf_dir, cache_dir, cfg), pdf_dir


def test_find_pdf_supports_relative_path(tmp_path: Path) -> None:
    service, pdf_dir = _make_service(tmp_path)
    target = pdf_dir / "sub" / "a.pdf"
    _create_pdf(target)

    resolved = service._find_pdf("sub/a.pdf")

    assert resolved == target


def test_find_pdf_rejects_invalid_or_unsafe_path(tmp_path: Path) -> None:
    service, _ = _make_service(tmp_path)

    assert service._find_pdf("../evil.pdf") is None
    assert service._find_pdf("/tmp/evil.pdf") is None
    assert service._find_pdf("C:/tmp/evil.pdf") is None
    assert service._find_pdf("not-pdf.txt") is None


def test_find_pdf_keeps_basename_compatibility(tmp_path: Path) -> None:
    service, pdf_dir = _make_service(tmp_path)
    target = pdf_dir / "nested" / "legacy.pdf"
    _create_pdf(target)

    resolved = service._find_pdf("legacy.pdf")

    assert resolved == target
