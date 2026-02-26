"""
命令行命令定义

提供命令行接口的各种命令实现。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def cmd_serve(args: argparse.Namespace) -> int:
    """
    启动Web服务器

    Args:
        args: 命令行参数

    Returns:
        退出码
    """
    from ipc_query.config import Config
    from ipc_query.api.server import create_server
    from ipc_query.utils.logger import setup_logging

    # 加载配置
    config = Config.from_args(args)
    config.ensure_directories()

    # 设置日志
    setup_logging(level=config.log_level, format_type=config.log_format)

    # 创建并启动服务器
    server = create_server(config)
    server.start()

    return 0


def cmd_build(args: argparse.Namespace) -> int:
    """
    构建数据库

    Args:
        args: 命令行参数

    Returns:
        退出码
    """
    from ipc_query.utils.logger import setup_logging, get_logger

    # 设置日志
    setup_logging(level="INFO", format_type="text")
    logger = get_logger("build")

    output_path = Path(args.output)

    # 收集PDF文件
    pdf_paths: list[Path] = []
    for p in args.pdf or []:
        pdf_paths.append(Path(p))
    for pattern in args.pdf_glob or []:
        for hit in sorted(Path(".").glob(pattern)):
            pdf_paths.append(Path(hit))
    for pdf_dir in args.pdf_dir or []:
        root = Path(pdf_dir)
        if not root.exists() or not root.is_dir():
            logger.error(f"PDF directory not found: {root}")
            return 2
        for hit in sorted(root.rglob("*")):
            if hit.is_file() and hit.suffix.lower() == ".pdf":
                pdf_paths.append(hit)

    # 如果没有指定PDF，使用默认
    if not pdf_paths:
        pdf_paths = _pick_default_pdfs(args.limit)

    # 去重
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in pdf_paths:
        key = str(p)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    pdf_paths = uniq

    # 检查文件存在
    missing = [str(p) for p in pdf_paths if not p.exists()]
    if missing:
        logger.error(f"Missing PDF files: {', '.join(missing)}")
        return 2

    logger.info(f"Building database with {len(pdf_paths)} PDFs...")

    # 调用构建函数
    from build_db import build_db
    build_db(output_path=output_path, pdf_paths=pdf_paths)

    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """
    命令行查询

    Args:
        args: 命令行参数

    Returns:
        退出码
    """
    from ipc_query.config import Config
    from ipc_query.db.connection import Database
    from ipc_query.db.repository import PartRepository
    from ipc_query.utils.logger import setup_logging

    setup_logging(level="INFO", format_type="text")

    config = Config.from_args(args)

    if not config.database_path.exists():
        print(f"Database not found: {config.database_path}")
        return 2

    db = Database(config.database_path, readonly=True)
    repo = PartRepository(db, config.pdf_dir)

    query = args.query
    limit = args.limit or 10

    # 执行搜索
    results, total = repo.search_by_pn(query, limit=limit)

    if not results:
        print(f"No results for: {query}")
        return 0

    print(f"Found {total} results for: {query}\n")

    for r in results[:limit]:
        pn = r.get("part_number_canonical") or r.get("part_number_cell") or "?"
        nom = r.get("nomenclature_preview", "")[:60]
        pdf = r.get("source_pdf", "")
        page = r.get("page_num", "")
        print(f"  {pn}")
        print(f"    {nom}")
        print(f"    {pdf} p.{page}")
        print()

    return 0


def _pick_default_pdfs(limit: int = 20) -> list[Path]:
    """选择默认PDF文件"""
    candidates = sorted(Path("IPC/7NG").glob("*___083.pdf"))
    candidates = [p for p in candidates if not p.name.endswith("-fm___083.pdf")]
    return candidates[:limit]


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="ipc_query",
        description="IPC零件目录查询系统",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.0.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # serve 命令
    serve_parser = subparsers.add_parser("serve", help="启动Web服务器")
    serve_parser.add_argument("--db", type=str, help="数据库文件路径")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="监听地址")
    serve_parser.add_argument("--port", type=int, default=8791, help="监听端口")
    serve_parser.add_argument("--pdf-dir", type=str, help="PDF文件目录")
    serve_parser.add_argument("--upload-dir", type=str, help="上传临时目录")
    serve_parser.add_argument("--debug", action="store_true", help="调试模式")

    # build 命令
    build_parser = subparsers.add_parser("build", help="构建数据库")
    build_parser.add_argument("--output", type=str, default="data/ipc.sqlite", help="输出数据库路径")
    build_parser.add_argument("--pdf", action="append", default=[], help="PDF文件路径")
    build_parser.add_argument("--pdf-glob", action="append", default=[], help="PDF文件glob模式")
    build_parser.add_argument("--pdf-dir", action="append", default=[], help="PDF目录（递归收集*.pdf）")
    build_parser.add_argument("--limit", type=int, default=20, help="默认处理的PDF数量")

    # query 命令
    query_parser = subparsers.add_parser("query", help="命令行查询")
    query_parser.add_argument("query", type=str, help="查询词")
    query_parser.add_argument("--db", type=str, help="数据库文件路径")
    query_parser.add_argument("--limit", type=int, default=10, help="结果数量限制")

    return parser


def main() -> int:
    """主入口"""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "serve": cmd_serve,
        "build": cmd_build,
        "query": cmd_query,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
