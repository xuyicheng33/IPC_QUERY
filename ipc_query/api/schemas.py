"""
API请求/响应模式定义
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SearchRequest:
    """搜索请求"""

    query: str
    match: str = "all"  # pn, term, all
    page: int = 1
    page_size: int = 20
    include_notes: bool = False


@dataclass
class SearchResponse:
    """搜索响应"""

    results: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    has_more: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": self.results,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "has_more": self.has_more,
        }


@dataclass
class PartDetailResponse:
    """零件详情响应"""

    part: dict[str, Any]
    parents: list[dict[str, Any]]
    siblings: list[dict[str, Any]]
    children: list[dict[str, Any]]
    xrefs: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "part": self.part,
            "parents": self.parents,
            "siblings": self.siblings,
            "children": self.children,
            "xrefs": self.xrefs,
        }


@dataclass
class ErrorResponse:
    """错误响应"""

    error: str
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "error": self.error,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class HealthResponse:
    """健康检查响应"""

    status: str
    version: str
    database: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "version": self.version,
            "database": self.database,
        }


@dataclass
class DocumentResponse:
    """文档响应"""

    id: int
    pdf_name: str
    pdf_path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pdf_name": self.pdf_name,
            "pdf_path": self.pdf_path,
            "created_at": self.created_at,
        }
