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
from urllib.parse import urlparse

from .exceptions import ConfigurationError


def _database_path_from_env() -> Path:
    """
    从环境变量解析数据库路径。

    优先级：
    1. DATABASE_PATH
    2. DATABASE_URL (仅支持 sqlite:...)
    3. 默认值 data/ipc.sqlite
    """
    db_path_raw = os.getenv("DATABASE_PATH", "").strip()
    if db_path_raw:
        return Path(db_path_raw)

    db_url_raw = os.getenv("DATABASE_URL", "").strip()
    if not db_url_raw:
        return Path("data/ipc.sqlite")

    parsed = urlparse(db_url_raw)
    if parsed.scheme != "sqlite":
        raise ConfigurationError(
            "DATABASE_URL must use sqlite scheme or set DATABASE_PATH",
            details={"database_url": db_url_raw},
        )

    if parsed.netloc in ("", "localhost"):
        if parsed.path:
            return Path(parsed.path)
        return Path("data/ipc.sqlite")

    if parsed.netloc and parsed.path:
        # sqlite://host/path 在这里被视为绝对路径 /path
        return Path(parsed.path)

    raise ConfigurationError(
        "Invalid DATABASE_URL format",
        details={"database_url": db_url_raw},
    )


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
    upload_dir: Path = field(default_factory=lambda: Path("data/pdfs"))
    cache_dir: Path = field(default_factory=lambda: Path("tmp/cache"))

    # 性能配置
    cache_size: int = 1000
    cache_ttl: int = 300  # 秒
    render_workers: int = 4
    render_timeout: float = 30.0
    render_semaphore: int = 4
    import_max_file_size_mb: int = 100
    import_queue_size: int = 8
    import_job_timeout_s: int = 600
    import_jobs_retained: int = 1000

    # 日志配置
    log_level: str = "INFO"
    log_format: str = "json"  # json | text

    # 搜索配置
    default_page_size: int = 20
    max_page_size: int = 100

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置"""
        pdf_dir_raw = os.getenv("PDF_DIR", "").strip()
        upload_dir_raw = os.getenv("UPLOAD_DIR", "").strip()
        pdf_dir = Path(pdf_dir_raw) if pdf_dir_raw else None
        upload_dir = Path(upload_dir_raw) if upload_dir_raw else (pdf_dir or Path("data/pdfs"))

        return cls(
            database_path=_database_path_from_env(),
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "8791")),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            static_dir=Path(os.getenv("STATIC_DIR", "web")),
            pdf_dir=pdf_dir,
            upload_dir=upload_dir,
            cache_dir=Path(os.getenv("CACHE_DIR", "tmp/cache")),
            cache_size=int(os.getenv("CACHE_SIZE", "1000")),
            cache_ttl=int(os.getenv("CACHE_TTL", "300")),
            render_workers=int(os.getenv("RENDER_WORKERS", "4")),
            render_timeout=float(os.getenv("RENDER_TIMEOUT", "30.0")),
            render_semaphore=int(os.getenv("RENDER_SEMAPHORE", "4")),
            import_max_file_size_mb=int(os.getenv("IMPORT_MAX_FILE_SIZE_MB", "100")),
            import_queue_size=int(os.getenv("IMPORT_QUEUE_SIZE", "8")),
            import_job_timeout_s=int(os.getenv("IMPORT_JOB_TIMEOUT_S", "600")),
            import_jobs_retained=int(os.getenv("IMPORT_JOBS_RETAINED", "1000")),
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
            # CLI 显式指定了 PDF 目录且未指定上传目录时，默认跟随 PDF 目录。
            if not (hasattr(args, "upload_dir") and args.upload_dir):
                config.upload_dir = config.pdf_dir
        if hasattr(args, "upload_dir") and args.upload_dir:
            config.upload_dir = Path(args.upload_dir)
        if hasattr(args, "static_dir") and args.static_dir:
            config.static_dir = Path(args.static_dir)
        if hasattr(args, "debug") and args.debug:
            config.debug = args.debug

        return config

    def ensure_directories(self) -> None:
        """确保必要的目录存在"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
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
            "upload_dir": str(self.upload_dir),
            "cache_dir": str(self.cache_dir),
            "cache_size": self.cache_size,
            "cache_ttl": self.cache_ttl,
            "render_workers": self.render_workers,
            "render_timeout": self.render_timeout,
            "import_max_file_size_mb": self.import_max_file_size_mb,
            "import_queue_size": self.import_queue_size,
            "import_job_timeout_s": self.import_job_timeout_s,
            "import_jobs_retained": self.import_jobs_retained,
            "log_level": self.log_level,
            "log_format": self.log_format,
        }
