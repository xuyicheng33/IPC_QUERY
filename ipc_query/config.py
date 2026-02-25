"""
配置管理模块

提供统一的配置管理，支持环境变量和命令行参数覆盖。
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Config:
    """应用配置"""

    # 数据库配置
    database_path: Path = field(default_factory=lambda: Path("data/ipc.sqlite"))

    # 服务配置
    host: str = "127.0.0.1"
    port: int = 8791
    debug: bool = False

    # 静态文件配置
    static_dir: Path = field(default_factory=lambda: Path("web"))
    pdf_dir: Path | None = None
    cache_dir: Path = field(default_factory=lambda: Path("tmp/cache"))

    # 性能配置
    cache_size: int = 1000
    cache_ttl: int = 300  # 秒
    render_workers: int = 4
    render_timeout: float = 30.0
    render_semaphore: int = 4

    # 日志配置
    log_level: str = "INFO"
    log_format: str = "json"  # json | text

    # 搜索配置
    default_page_size: int = 20
    max_page_size: int = 100

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置"""
        return cls(
            database_path=Path(os.getenv("DATABASE_PATH", "data/ipc.sqlite")),
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "8791")),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            static_dir=Path(os.getenv("STATIC_DIR", "web")),
            pdf_dir=Path(p) if (p := os.getenv("PDF_DIR")) else None,
            cache_dir=Path(os.getenv("CACHE_DIR", "tmp/cache")),
            cache_size=int(os.getenv("CACHE_SIZE", "1000")),
            cache_ttl=int(os.getenv("CACHE_TTL", "300")),
            render_workers=int(os.getenv("RENDER_WORKERS", "4")),
            render_timeout=float(os.getenv("RENDER_TIMEOUT", "30.0")),
            render_semaphore=int(os.getenv("RENDER_SEMAPHORE", "4")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "json"),
            default_page_size=int(os.getenv("DEFAULT_PAGE_SIZE", "20")),
            max_page_size=int(os.getenv("MAX_PAGE_SIZE", "100")),
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "Config":
        """从命令行参数加载配置"""
        config = cls.from_env()

        # 命令行参数覆盖
        if hasattr(args, "db") and args.db:
            config.database_path = Path(args.db)
        if hasattr(args, "host") and args.host:
            config.host = args.host
        if hasattr(args, "port") and args.port:
            config.port = args.port
        if hasattr(args, "pdf_dir") and args.pdf_dir:
            config.pdf_dir = Path(args.pdf_dir)
        if hasattr(args, "static_dir") and args.static_dir:
            config.static_dir = Path(args.static_dir)
        if hasattr(args, "debug") and args.debug:
            config.debug = args.debug

        return config

    def ensure_directories(self) -> None:
        """确保必要的目录存在"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.pdf_dir:
            self.pdf_dir.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于日志和调试）"""
        return {
            "database_path": str(self.database_path),
            "host": self.host,
            "port": self.port,
            "debug": self.debug,
            "static_dir": str(self.static_dir),
            "pdf_dir": str(self.pdf_dir) if self.pdf_dir else None,
            "cache_dir": str(self.cache_dir),
            "cache_size": self.cache_size,
            "cache_ttl": self.cache_ttl,
            "render_workers": self.render_workers,
            "render_timeout": self.render_timeout,
            "log_level": self.log_level,
            "log_format": self.log_format,
        }
