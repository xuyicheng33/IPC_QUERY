"""
CLI命令测试
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from cli.commands import cmd_build, create_parser


def test_build_parser_accepts_pdf_dir() -> None:
    parser = create_parser()
    args = parser.parse_args(["build", "--pdf-dir", "./pdfs", "--output", "./data/ipc.sqlite"])
    assert args.command == "build"
    assert args.pdf_dir == ["./pdfs"]
    assert args.output == "./data/ipc.sqlite"


def test_cmd_build_collects_pdf_from_pdf_dir(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    (pdf_dir / "a.pdf").write_bytes(b"pdf-a")
    nested = pdf_dir / "nested"
    nested.mkdir()
    (nested / "b.PDF").write_bytes(b"pdf-b")
    (nested / "ignore.txt").write_text("x", encoding="utf-8")

    args = Namespace(
        output=str(tmp_path / "out.sqlite"),
        pdf=[],
        pdf_glob=[],
        pdf_dir=[str(pdf_dir)],
        limit=20,
    )

    with patch("build_db.build_db") as mock_build:
        rc = cmd_build(args)

    assert rc == 0
    assert mock_build.call_count == 1
    passed_paths = mock_build.call_args.kwargs["pdf_paths"]
    passed_names = sorted(p.name for p in passed_paths)
    assert passed_names == ["a.pdf", "b.PDF"]
