"""
API请求处理器

处理HTTP请求并返回响应。
"""

from __future__ import annotations

import json
import mimetypes
import re
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from ..config import Config
from ..db.connection import Database
from ..db.repository import DocumentRepository, PartRepository
from ..exceptions import IpcQueryError, NotFoundError, PartNotFoundError
from ..services.render import RenderService
from ..services.search import SearchService
from ..utils.logger import get_logger
from ..utils.metrics import metrics

logger = get_logger(__name__)


def _json_bytes(obj: Any) -> bytes:
    """将对象转换为JSON字节"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _safe_int(value: str | None, default: int) -> int:
    """安全解析整数"""
    try:
        return int(value) if value is not None else default
    except Exception:
        return default


class ApiHandlers:
    """
    API请求处理器

    处理所有API请求，包括搜索、详情、文档列表等。
    """

    def __init__(
        self,
        search_service: SearchService,
        render_service: RenderService,
        doc_repo: DocumentRepository,
        db: Database,
        config: Config,
    ):
        self._search = search_service
        self._render = render_service
        self._docs = doc_repo
        self._db = db
        self._config = config

    def handle_search(self, query_string: str) -> tuple[int, bytes, str]:
        """
        处理搜索请求

        GET /api/search?q=...&match=...&page=...
        """
        qs = parse_qs(query_string) if query_string else {}

        q = (qs.get("q") or [""])[0].strip()
        match = (qs.get("match") or ["all"])[0]
        page = _safe_int((qs.get("page") or [None])[0], 1)
        page_size = _safe_int((qs.get("page_size") or [None])[0], 0)
        include_notes = (qs.get("include_notes") or ["0"])[0] == "1"

        if page_size <= 0:
            page_size = _safe_int((qs.get("limit") or [None])[0], 60)

        result = self._search.search(
            query=q,
            match=match,
            page=page,
            page_size=page_size,
            include_notes=include_notes,
        )

        return HTTPStatus.OK, _json_bytes(result), "application/json; charset=utf-8"

    def handle_part(self, part_id_str: str) -> tuple[int, bytes, str]:
        """
        处理零件详情请求

        GET /api/part/{id}
        """
        try:
            part_id = int(part_id_str)
        except ValueError:
            raise NotFoundError("Invalid part ID")

        result = self._search.get_part_detail(part_id)
        if result is None:
            raise PartNotFoundError(int(part_id_str) if part_id_str.isdigit() else 0)

        return HTTPStatus.OK, _json_bytes(result), "application/json; charset=utf-8"

    def handle_docs(self) -> tuple[int, bytes, str]:
        """
        处理文档列表请求

        GET /api/docs
        """
        docs = self._docs.get_all()
        result = [d.to_dict() for d in docs]
        return HTTPStatus.OK, _json_bytes(result), "application/json; charset=utf-8"

    def handle_health(self) -> tuple[int, bytes, str]:
        """
        处理健康检查请求

        GET /api/health
        """
        result = {
            "status": "healthy",
            "version": "2.0.0",
            "database": self._db.check_health(),
        }
        return HTTPStatus.OK, _json_bytes(result), "application/json; charset=utf-8"

    def handle_metrics(self) -> tuple[int, bytes, str]:
        """
        处理指标请求

        GET /api/metrics
        """
        result = metrics.export()
        return HTTPStatus.OK, _json_bytes(result), "application/json; charset=utf-8"

    def handle_render(
        self,
        pdf_name: str,
        page_str: str,
    ) -> tuple[int, bytes | Path, str]:
        """
        处理渲染请求

        GET /render/{pdf}/{page}.png
        """
        try:
            page = int(page_str.replace(".png", ""))
        except ValueError:
            raise NotFoundError("Invalid page number")

        # 渲染页面
        cache_path = self._render.render_page(pdf_name, page, scale=2.0)

        return HTTPStatus.OK, cache_path, "image/png"

    def handle_pdf(self, pdf_name: str, range_header: str | None) -> tuple[int, bytes | Path, str, dict[str, str]]:
        """
        处理PDF文件请求

        GET /pdf/{name}
        """
        # 查找PDF文件
        pdf_path = self._render._find_pdf(pdf_name)
        if pdf_path is None or not pdf_path.exists():
            raise NotFoundError(f"PDF not found: {pdf_name}")

        size = int(pdf_path.stat().st_size)
        content_type = "application/pdf"
        extra_headers = {
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{pdf_name}"',
        }

        # 处理范围请求
        if range_header:
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if m:
                start_raw, end_raw = m.group(1), m.group(2)
                try:
                    if start_raw == "" and end_raw == "":
                        raise ValueError("empty range")
                    if start_raw == "":
                        length = int(end_raw)
                        start = max(size - length, 0)
                        end = size - 1
                    else:
                        start = int(start_raw)
                        end = int(end_raw) if end_raw != "" else size - 1
                        if start < 0 or start >= size:
                            raise ValueError("start out of range")
                        end = min(max(end, start), size - 1)

                    # 返回部分内容（这里简化处理，返回完整文件）
                    # 实际实现需要读取文件片段
                    return HTTPStatus.PARTIAL_CONTENT, pdf_path, content_type, {
                        **extra_headers,
                        "Content-Range": f"bytes {start}-{end}/{size}",
                    }
                except Exception:
                    pass

        return HTTPStatus.OK, pdf_path, content_type, extra_headers

    def handle_static(self, path: str) -> tuple[int, bytes | Path, str]:
        """
        处理静态文件请求

        GET /static/{path} 或 GET /
        """
        if not path or path == "/":
            target = self._config.static_dir / "index.html"
        else:
            rel = path.lstrip("/")
            target = (self._config.static_dir / rel).resolve()
            static_root = self._config.static_dir.resolve()

            # 安全检查：防止目录遍历
            if static_root not in target.parents and target != static_root:
                return HTTPStatus.FORBIDDEN, _json_bytes({"error": "forbidden"}), "application/json"

        if not target.exists() or not target.is_file():
            return HTTPStatus.NOT_FOUND, _json_bytes({"error": "not_found"}), "application/json"

        # 确定内容类型
        ct = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.suffix == ".html":
            ct = "text/html; charset=utf-8"
        elif target.suffix == ".js":
            ct = "application/javascript; charset=utf-8"
        elif target.suffix == ".css":
            ct = "text/css; charset=utf-8"

        return HTTPStatus.OK, target, ct

    def handle_error(self, error: Exception) -> tuple[int, bytes, str]:
        """
        处理错误

        将异常转换为HTTP响应。
        """
        if isinstance(error, IpcQueryError):
            status = HTTPStatus.BAD_REQUEST
            if isinstance(error, NotFoundError):
                status = HTTPStatus.NOT_FOUND
            return status, _json_bytes(error.to_dict()), "application/json"

        # 未知错误
        logger.exception("Unhandled error")
        return HTTPStatus.INTERNAL_SERVER_ERROR, _json_bytes({
            "error": "INTERNAL_ERROR",
            "message": "Internal server error",
        }), "application/json"
