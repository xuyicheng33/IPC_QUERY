"""
日志配置模块

提供结构化的日志系统，支持 JSON 和文本两种格式。
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    JSON 格式化器

    将日志记录格式化为 JSON，便于日志聚合和分析。
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加额外字段
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        # 添加异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            log_entry["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None

        return json.dumps(log_entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """
    文本格式化器

    人类可读的日志格式，适合开发环境。
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        base = f"[{timestamp}] [{record.levelname:5}] [{record.name}] {record.getMessage()}"

        # 添加额外字段
        if hasattr(record, "extra_fields") and record.extra_fields:
            extra_str = " ".join(f"{k}={v}" for k, v in record.extra_fields.items())
            base = f"{base} | {extra_str}"

        # 添加异常信息
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"

        return base


class ExtraLogAdapter(logging.LoggerAdapter):
    """
    日志适配器

    支持添加额外字段的日志适配器。
    """

    def process(
        self,
        msg: str,
        kwargs: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        extra_fields = kwargs.pop("extra_fields", {})
        if self.extra:
            extra_fields.update(self.extra)

        if extra_fields:
            kwargs["extra"] = kwargs.get("extra", {})
            kwargs["extra"]["extra_fields"] = extra_fields

        return msg, kwargs


def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    stream: Any = None,
) -> None:
    """
    配置日志系统

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: 日志格式 (json, text)
        stream: 输出流，默认为 sys.stderr
    """
    if stream is None:
        stream = sys.stderr

    handler = logging.StreamHandler(stream)

    if format_type.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    # 配置根日志器
    root_logger = logging.root
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper()))


def get_logger(
    name: str,
    extra: dict[str, Any] | None = None,
) -> ExtraLogAdapter:
    """
    获取日志器

    Args:
        name: 日志器名称
        extra: 额外字段

    Returns:
        日志适配器
    """
    logger = logging.getLogger(name)
    return ExtraLogAdapter(logger, extra or {})


class LogContext:
    """
    日志上下文管理器

    用于在代码块中添加额外的日志字段。
    """

    def __init__(self, logger: ExtraLogAdapter, **fields: Any):
        self.logger = logger
        self.fields = fields
        self.original_extra = logger.extra.copy()

    def __enter__(self) -> "LogContext":
        self.logger.extra.update(self.fields)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.logger.extra = self.original_extra
