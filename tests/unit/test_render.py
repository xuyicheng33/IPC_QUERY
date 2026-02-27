from __future__ import annotations

from pathlib import Path

import fitz

from ipc_query.config import Config
from ipc_query.services.render import create_render_service


def _create_pdf(path: Path, *, pages: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for _ in range(max(1, int(pages))):
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


def test_render_cache_key_avoids_relative_path_collisions(tmp_path: Path) -> None:
    service, pdf_dir = _make_service(tmp_path)
    path_a = pdf_dir / "a" / "b.pdf"
    path_b = pdf_dir / "a_b.pdf"
    _create_pdf(path_a)
    _create_pdf(path_b)

    cache_a = service.render_page("a/b.pdf", 1, scale=2.0)
    cache_b = service.render_page("a_b.pdf", 1, scale=2.0)

    assert cache_a.exists()
    assert cache_b.exists()
    assert cache_a != cache_b


def test_render_cache_invalidates_when_pdf_changes(tmp_path: Path) -> None:
    service, pdf_dir = _make_service(tmp_path)
    target = pdf_dir / "doc.pdf"
    _create_pdf(target, pages=1)
    old_cache = service.render_page("doc.pdf", 1, scale=2.0)

    _create_pdf(target, pages=2)
    new_cache = service.render_page("doc.pdf", 1, scale=2.0)

    assert old_cache.exists()
    assert new_cache.exists()
    assert old_cache != new_cache


def test_render_cache_keeps_latest_two_versions(tmp_path: Path) -> None:
    service, pdf_dir = _make_service(tmp_path)
    target = pdf_dir / "doc.pdf"

    _create_pdf(target, pages=1)
    first = service.render_page("doc.pdf", 1, scale=2.0)
    _create_pdf(target, pages=2)
    second = service.render_page("doc.pdf", 1, scale=2.0)
    _create_pdf(target, pages=3)
    third = service.render_page("doc.pdf", 1, scale=2.0)

    prefix = service._cache_identity("doc.pdf", target)
    versions = sorted((service._cache_dir).glob(f"{prefix}_1_2.0_*.png"))
    assert len(versions) <= 2
    assert second.exists() or third.exists()
    assert third.exists()
    assert first not in versions
