"""
异常定义模块

定义系统中所有自定义异常类，提供统一的错误处理机制。
"""

from __future__ import annotations

from typing import Any


class IpcQueryError(Exception):
    """
    基础异常类

    所有自定义异常都继承此类，提供统一的错误码和消息格式。

    Attributes:
        message: 错误消息
        code: 错误码
        details: 额外的错误详情
    """

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN",
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式（用于API响应）"""
        result: dict[str, Any] = {
            "error": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


class ConfigurationError(IpcQueryError):
    """配置错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="CONFIGURATION_ERROR", details=details)


class DatabaseError(IpcQueryError):
    """数据库操作错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="DATABASE_ERROR", details=details)


class DatabaseConnectionError(DatabaseError):
    """数据库连接错误"""

    def __init__(self, message: str = "Failed to connect to database"):
        super().__init__(message)


class DatabaseQueryError(DatabaseError):
    """数据库查询错误"""

    def __init__(self, message: str, query: str | None = None):
        details = {"query": query} if query else None
        super().__init__(message, details=details)


class SearchError(IpcQueryError):
    """搜索错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="SEARCH_ERROR", details=details)


class InvalidSearchQueryError(SearchError):
    """无效的搜索查询"""

    def __init__(self, message: str = "Invalid search query"):
        super().__init__(message)


class RenderError(IpcQueryError):
    """PDF渲染错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="RENDER_ERROR", details=details)


class PdfNotFoundError(RenderError):
    """PDF文件未找到"""

    def __init__(self, pdf_name: str):
        super().__init__(
            f"PDF file not found: {pdf_name}",
            details={"pdf_name": pdf_name},
        )


class PageNotFoundError(RenderError):
    """页面未找到"""

    def __init__(self, pdf_name: str, page: int):
        super().__init__(
            f"Page {page} not found in PDF: {pdf_name}",
            details={"pdf_name": pdf_name, "page": page},
        )


class PdfParseError(IpcQueryError):
    """PDF解析错误"""

    def __init__(self, message: str, pdf_path: str | None = None):
        details = {"pdf_path": pdf_path} if pdf_path else None
        super().__init__(message, code="PDF_PARSE_ERROR", details=details)


class NotFoundError(IpcQueryError):
    """资源未找到错误"""

    def __init__(self, message: str, resource_type: str | None = None):
        details = {"resource_type": resource_type} if resource_type else None
        super().__init__(message, code="NOT_FOUND", details=details)


class PartNotFoundError(NotFoundError):
    """零件未找到"""

    def __init__(self, part_id: int):
        super().__init__(
            f"Part not found: {part_id}",
            resource_type="part",
        )
        self.part_id = part_id


class ValidationError(IpcQueryError):
    """验证错误"""

    def __init__(self, message: str, field: str | None = None):
        details = {"field": field} if field else None
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class ConflictError(IpcQueryError):
    """资源冲突错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="CONFLICT", details=details)


class RateLimitError(IpcQueryError):
    """请求频率限制错误"""

    def __init__(self, message: str = "Too many requests", retry_after: int | None = None):
        details = {"retry_after": retry_after} if retry_after else None
        super().__init__(message, code="RATE_LIMITED", details=details)
