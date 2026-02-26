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
from ..db.repository import DocumentRepository
from ..exceptions import IpcQueryError, NotFoundError, PartNotFoundError
from ..exceptions import ValidationError
from ..services.importer import ImportService
from ..services.render import RenderService
from ..services.scanner import ScanService
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
        import_service: ImportService | None = None,
        scan_service: ScanService | None = None,
    ):
        self._search = search_service
        self._render = render_service
        self._docs = doc_repo
        self._db = db
        self._config = config
        self._import = import_service
        self._scan = scan_service

    def import_enabled(self) -> bool:
        """导入服务是否可用。"""
        return self._import is not None

    def handle_search(self, query_string: str) -> tuple[int, bytes, str]:
        """
        处理搜索请求

        GET /api/search?q=...&match=...&page=...
        """
        qs = parse_qs(query_string) if query_string else {}

        q = (qs.get("q") or [""])[0].strip()
        match = (qs.get("match") or ["all"])[0]
        page_raw = (qs.get("page") or [""])[0]
        page_size_raw = (qs.get("page_size") or [""])[0]
        page = _safe_int(page_raw, 1)
        page_size = _safe_int(page_size_raw, 0)
        include_notes = (qs.get("include_notes") or ["0"])[0] == "1"
        source_pdf = (qs.get("source_pdf") or [""])[0].strip()
        source_dir = (qs.get("source_dir") or [""])[0].strip()
        if page <= 0:
            page = 1

        if page_size <= 0:
            page_size = _safe_int((qs.get("limit") or [""])[0], 60)
        if page_size <= 0:
            page_size = 60

        result = self._search.search(
            query=q,
            match=match,
            page=page,
            page_size=page_size,
            include_notes=include_notes,
            source_pdf=source_pdf,
            source_dir=source_dir,
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

    def handle_docs_tree(self, path: str = "") -> tuple[int, bytes, str]:
        rel = self._normalize_relative_dir(path, allow_empty=True)
        root = self._require_pdf_root()
        target = root if not rel else root / rel
        if not target.exists() or not target.is_dir():
            raise NotFoundError(f"Folder not found: {rel or '/'}")

        docs_by_rel: dict[str, dict[str, Any]] = {}
        docs_by_name: dict[str, dict[str, Any]] = {}
        for d in self._docs.get_all():
            payload = d.to_dict()
            rp = str(payload.get("relative_path") or payload.get("pdf_name") or "").replace("\\", "/").strip("/")
            name = str(payload.get("pdf_name") or "").strip()
            if rp:
                docs_by_rel[rp] = payload
            if name and name not in docs_by_name:
                docs_by_name[name] = payload

        dirs: list[dict[str, Any]] = []
        files: list[dict[str, Any]] = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.is_dir():
                child_rel = child.resolve().relative_to(root.resolve()).as_posix()
                dirs.append({"name": child.name, "path": child_rel})
                continue

            if not child.is_file() or child.suffix.lower() != ".pdf":
                continue

            rel_path = child.resolve().relative_to(root.resolve()).as_posix()
            db_doc = docs_by_rel.get(rel_path) or docs_by_name.get(child.name)
            files.append(
                {
                    "name": child.name,
                    "relative_path": rel_path,
                    "indexed": db_doc is not None,
                    "document": db_doc,
                }
            )

        return HTTPStatus.OK, _json_bytes({"path": rel, "directories": dirs, "files": files}), "application/json; charset=utf-8"

    def handle_doc_delete(self, pdf_name: str) -> tuple[int, bytes, str]:
        """
        处理文档删除请求

        DELETE /api/docs?name=... 或 DELETE /api/docs/{pdf_name}
        """
        if self._import is None:
            raise ValidationError("Import service is not enabled")

        result = self._import.delete_document(pdf_name)
        if not result.get("deleted"):
            raise NotFoundError(f"PDF not found: {pdf_name}")
        return HTTPStatus.OK, _json_bytes(result), "application/json; charset=utf-8"

    def handle_health(self) -> tuple[int, bytes, str]:
        """
        处理健康检查请求

        GET /api/health
        """
        database = self._db.check_health()
        status = "healthy" if database.get("status") == "healthy" else "unhealthy"
        result = {
            "status": status,
            "version": "2.0.0",
            "database": database,
        }
        return HTTPStatus.OK, _json_bytes(result), "application/json; charset=utf-8"

    def handle_metrics(self) -> tuple[int, bytes, str]:
        """
        处理指标请求

        GET /api/metrics
        """
        result = metrics.export()
        return HTTPStatus.OK, _json_bytes(result), "application/json; charset=utf-8"

    def handle_import_submit(
        self,
        filename: str,
        payload: bytes,
        content_type: str | None,
        target_dir: str = "",
    ) -> tuple[int, bytes, str]:
        """
        处理导入请求

        POST /api/import
        """
        if self._import is None:
            raise ValidationError("Import service is not enabled")
        job = self._import.submit_upload(
            filename=filename,
            payload=payload,
            content_type=content_type,
            target_dir=target_dir,
        )
        return HTTPStatus.ACCEPTED, _json_bytes(job), "application/json; charset=utf-8"

    def handle_folder_create(self, path: str, name: str) -> tuple[int, bytes, str]:
        root = self._require_pdf_root()
        parent = self._normalize_relative_dir(path, allow_empty=True)
        folder_name = self._normalize_folder_name(name)
        base = root if not parent else root / parent
        if not base.exists() or not base.is_dir():
            raise NotFoundError(f"Folder not found: {parent or '/'}")
        new_dir = base / folder_name
        new_dir.mkdir(parents=False, exist_ok=True)
        rel = new_dir.resolve().relative_to(root.resolve()).as_posix()
        return HTTPStatus.CREATED, _json_bytes({"created": True, "path": rel}), "application/json; charset=utf-8"

    def handle_scan_submit(self, path: str = "") -> tuple[int, bytes, str]:
        if self._scan is None:
            raise ValidationError("Scan service is not enabled")
        job = self._scan.submit_scan(path=path)
        return HTTPStatus.ACCEPTED, _json_bytes(job), "application/json; charset=utf-8"

    def handle_scan_job(self, job_id: str) -> tuple[int, bytes, str]:
        if self._scan is None:
            raise ValidationError("Scan service is not enabled")
        job = self._scan.get_job(job_id)
        if not job:
            raise NotFoundError(f"Scan job not found: {job_id}")
        return HTTPStatus.OK, _json_bytes(job), "application/json; charset=utf-8"

    def handle_import_job(self, job_id: str) -> tuple[int, bytes, str]:
        """
        处理单个导入任务查询

        GET /api/import/{job_id}
        """
        if self._import is None:
            raise ValidationError("Import service is not enabled")
        job = self._import.get_job(job_id)
        if not job:
            raise NotFoundError(f"Import job not found: {job_id}")
        return HTTPStatus.OK, _json_bytes(job), "application/json; charset=utf-8"

    def handle_import_jobs(self, limit: int = 20) -> tuple[int, bytes, str]:
        """
        处理导入任务列表查询

        GET /api/import/jobs
        """
        if self._import is None:
            raise ValidationError("Import service is not enabled")
        jobs = self._import.list_jobs(limit=limit)
        return HTTPStatus.OK, _json_bytes({"jobs": jobs}), "application/json; charset=utf-8"

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
                        if length <= 0:
                            raise ValueError("invalid suffix length")
                        start = max(size - length, 0)
                        end = size - 1
                    else:
                        start = int(start_raw)
                        end = int(end_raw) if end_raw != "" else size - 1
                        if start < 0 or start >= size:
                            raise ValueError("start out of range")
                        if end_raw != "" and end < start:
                            raise ValueError("end before start")
                        end = min(end, size - 1)

                    chunk_len = (end - start) + 1
                    with pdf_path.open("rb") as f:
                        f.seek(start)
                        payload = f.read(chunk_len)

                    return HTTPStatus.PARTIAL_CONTENT, payload, content_type, {
                        **extra_headers,
                        "Content-Range": f"bytes {start}-{end}/{size}",
                    }
                except Exception:
                    return HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, b"", content_type, {
                        **extra_headers,
                        "Content-Range": f"bytes */{size}",
                    }

        return HTTPStatus.OK, pdf_path, content_type, extra_headers

    def handle_static(self, path: str) -> tuple[int, bytes | Path, str]:
        """
        处理静态文件请求

        GET /static/{path} 或 GET /
        """
        if path == "/search":
            path = "/search.html"
        elif path == "/db":
            path = "/db.html"
        elif re.fullmatch(r"/part/\d+", path):
            path = "/part.html"

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

    def _require_pdf_root(self) -> Path:
        pdf_dir = self._config.pdf_dir
        if pdf_dir is None:
            raise ValidationError("PDF directory is not configured")
        return pdf_dir

    def _normalize_relative_dir(self, path: str, *, allow_empty: bool) -> str:
        raw = (path or "").replace("\\", "/").strip().strip("/")
        if not raw:
            if allow_empty:
                return ""
            raise ValidationError("Missing path")
        parts = [p for p in raw.split("/") if p]
        if any(p in {".", ".."} for p in parts):
            raise ValidationError("Invalid path")
        return "/".join(parts)

    def _normalize_folder_name(self, name: str) -> str:
        raw = (name or "").replace("\\", "/").strip().strip("/")
        if not raw:
            raise ValidationError("Missing folder name")
        if "/" in raw:
            raise ValidationError("Folder name must not contain '/'")
        if raw in {".", ".."}:
            raise ValidationError("Invalid folder name")
        return raw
