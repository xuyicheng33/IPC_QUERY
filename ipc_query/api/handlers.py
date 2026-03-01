"""
API请求处理器

处理HTTP请求并返回响应。
"""

from __future__ import annotations

import json
import mimetypes
import re
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from ..config import Config
from ..constants import VERSION
from ..db.connection import Database
from ..db.repository import DocumentRepository
from ..exceptions import (
    ConflictError,
    DatabaseError,
    IpcQueryError,
    NotFoundError,
    PartNotFoundError,
    RateLimitError,
    RenderError,
    SearchError,
    UnauthorizedError,
    ValidationError,
)
from ..services.importer import ImportService
from ..services.render import RenderService
from ..services.scanner import ScanService
from ..services.search import SearchService
from ..utils.logger import get_logger
from ..utils.metrics import metrics

logger = get_logger(__name__)


@dataclass(frozen=True)
class PdfRangePayload:
    """PDF 范围响应元数据（由 RequestHandler 负责流式输出内容）。"""

    path: Path
    start: int
    end: int
    total_size: int


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
        import_enabled: bool | None = None,
        scan_enabled: bool | None = None,
        import_reason: str = "",
        scan_reason: str = "",
        path_policy_warning_count: int = 0,
    ):
        self._search = search_service
        self._render = render_service
        self._docs = doc_repo
        self._db = db
        self._config = config
        self._import = import_service
        self._scan = scan_service
        self._import_enabled = bool(import_enabled) if import_enabled is not None else (import_service is not None)
        self._scan_enabled = bool(scan_enabled) if scan_enabled is not None else (scan_service is not None)
        self._import_reason = str(import_reason or "")
        self._scan_reason = str(scan_reason or "")
        self._path_policy_warning_count = max(0, int(path_policy_warning_count))

    def import_enabled(self) -> bool:
        """导入服务是否可用。"""
        return self._import_enabled

    def scan_enabled(self) -> bool:
        """扫描服务是否可用。"""
        return self._scan_enabled

    def handle_capabilities(self) -> tuple[int, bytes, str]:
        write_mode = (self._config.write_api_auth_mode or "disabled").strip().lower()
        write_required = write_mode == "api_key"
        payload = {
            "import_enabled": self.import_enabled(),
            "scan_enabled": self.scan_enabled(),
            "import_reason": "" if self.import_enabled() else self._import_reason,
            "scan_reason": "" if self.scan_enabled() else self._scan_reason,
            "write_auth_mode": write_mode,
            "write_auth_required": write_required,
            "legacy_folder_routes_enabled": bool(self._config.legacy_folder_routes_enabled),
            "directory_policy": "single_level",
            "path_policy_warning_count": self._path_policy_warning_count,
        }
        return HTTPStatus.OK, _json_bytes(payload), "application/json; charset=utf-8"

    def handle_search(self, query_string: str) -> tuple[int, bytes, str]:
        """
        处理搜索请求

        GET /api/search?q=...&match=...&page=...
        """
        qs = parse_qs(query_string) if query_string else {}

        q = (qs.get("q") or [""])[0].strip()
        match = (qs.get("match") or ["all"])[0]
        sort = (qs.get("sort") or ["relevance"])[0]
        page_raw = (qs.get("page") or [""])[0]
        page_size_raw = (qs.get("page_size") or [""])[0]
        page = _safe_int(page_raw, 1)
        page_size = _safe_int(page_size_raw, 0)
        include_notes = (qs.get("include_notes") or ["0"])[0] == "1"
        source_pdf = (qs.get("source_pdf") or [""])[0].strip()
        source_dir = (qs.get("source_dir") or [""])[0].strip()
        configured_default_page_size = _safe_int(str(self._config.default_page_size), 20)
        if page <= 0:
            page = 1

        if page_size <= 0:
            page_size = _safe_int((qs.get("limit") or [""])[0], configured_default_page_size)
        if page_size <= 0:
            page_size = configured_default_page_size

        result = self._search.search(
            query=q,
            match=match,
            sort=sort,
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
        rel = self._normalize_relative_dir(path, allow_empty=True, max_depth=1, field_name="path")
        root = self._require_pdf_root()
        target = root if not rel else root / rel
        if not target.exists() or not target.is_dir():
            raise NotFoundError(f"Folder not found: {rel or '/'}")

        docs_by_rel: dict[str, dict[str, Any]]
        lookup_fn = getattr(self._docs, "get_lookup_for_dir", None)
        if callable(lookup_fn):
            docs_by_rel, _ = lookup_fn(rel)
        else:
            docs_by_rel = {}
            for d in self._docs.get_all():
                payload = d.to_dict()
                rp = str(payload.get("relative_path") or payload.get("pdf_name") or "").replace("\\", "/").strip("/")
                if rp:
                    docs_by_rel[rp] = payload

        dirs: list[dict[str, Any]] = []
        files: list[dict[str, Any]] = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.is_dir():
                if rel:
                    # 当前只支持一级目录：进入子目录后不再展示目录列表。
                    continue
                child_rel = child.resolve().relative_to(root.resolve()).as_posix()
                dirs.append({"name": child.name, "path": child_rel})
                continue

            if not child.is_file() or child.suffix.lower() != ".pdf":
                continue

            rel_path = child.resolve().relative_to(root.resolve()).as_posix()
            db_doc = docs_by_rel.get(rel_path)
            safe_doc = self._sanitize_document_payload(db_doc)
            files.append(
                {
                    "name": child.name,
                    "relative_path": rel_path,
                    "indexed": safe_doc is not None,
                    "document": safe_doc,
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

    def handle_doc_rename(self, path: str, new_name: str) -> tuple[int, bytes, str]:
        """
        重命名文档请求

        POST /api/docs/rename
        body: {"path": "dir/a.pdf", "new_name": "b.pdf"}
        """
        if self._import is None:
            raise ValidationError("Import service is not enabled")
        result = self._import.rename_document(path=path, new_name=new_name)
        if not result.get("updated"):
            raise NotFoundError(f"PDF not found: {path}")
        return HTTPStatus.OK, _json_bytes(result), "application/json; charset=utf-8"

    def handle_doc_move(self, path: str, target_dir: str) -> tuple[int, bytes, str]:
        """
        移动文档请求

        POST /api/docs/move
        body: {"path": "dir/a.pdf", "target_dir": "other/sub"}
        """
        if self._import is None:
            raise ValidationError("Import service is not enabled")
        result = self._import.move_document(path=path, target_dir=target_dir)
        if not result.get("updated"):
            raise NotFoundError(f"PDF not found: {path}")
        return HTTPStatus.OK, _json_bytes(result), "application/json; charset=utf-8"

    def handle_docs_batch_delete(self, paths: list[Any]) -> tuple[int, bytes, str]:
        """
        批量删除文档请求

        POST /api/docs/batch-delete
        body: {"paths": ["a.pdf", "sub/b.pdf"]}
        """
        if self._import is None:
            raise ValidationError("Import service is not enabled")
        if not isinstance(paths, list):
            raise ValidationError("`paths` must be an array")
        if len(paths) == 0:
            raise ValidationError("`paths` must not be empty")

        results: list[dict[str, Any]] = []
        deleted = 0

        for raw_path in paths:
            if not isinstance(raw_path, str):
                results.append({
                    "path": str(raw_path),
                    "ok": False,
                    "error": "path must be a string",
                    "error_code": "VALIDATION_ERROR",
                })
                continue

            path = raw_path.strip()
            if not path:
                results.append({
                    "path": path,
                    "ok": False,
                    "error": "Missing filename",
                    "error_code": "VALIDATION_ERROR",
                })
                continue

            try:
                detail = self._import.delete_document(path)
                if detail.get("deleted"):
                    deleted += 1
                    results.append({"path": path, "ok": True, "detail": detail})
                else:
                    results.append({
                        "path": path,
                        "ok": False,
                        "error": f"PDF not found: {path}",
                        "error_code": "NOT_FOUND",
                    })
            except (ValidationError, NotFoundError, ConflictError) as e:
                item = {
                    "path": path,
                    "ok": False,
                    "error": str(e),
                    "error_code": getattr(e, "code", "VALIDATION_ERROR"),
                }
                details = getattr(e, "details", None)
                if details:
                    item["details"] = details
                results.append(item)
            except Exception as e:
                logger.exception("Batch delete failed", extra_fields={"path": path})
                results.append({
                    "path": path,
                    "ok": False,
                    "error": str(e),
                    "error_code": "INTERNAL_ERROR",
                })

        total = len(paths)
        payload = {
            "total": total,
            "deleted": deleted,
            "failed": total - deleted,
            "results": results,
        }
        return HTTPStatus.OK, _json_bytes(payload), "application/json; charset=utf-8"

    def handle_health(self) -> tuple[int, bytes, str]:
        """
        处理健康检查请求

        GET /api/health
        """
        database = self._db.check_health()
        status = "healthy" if database.get("status") == "healthy" else "unhealthy"
        result = {
            "status": status,
            "version": VERSION,
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
        parent = self._normalize_relative_dir(path, allow_empty=True)
        if parent:
            raise ValidationError("Only root folder supports create")

        root = self._require_pdf_root()
        folder_name = self._normalize_folder_name(name)
        base = root if not parent else root / parent
        if not base.exists() or not base.is_dir():
            raise NotFoundError(f"Folder not found: {parent or '/'}")
        new_dir = base / folder_name
        new_dir.mkdir(parents=False, exist_ok=True)
        rel = new_dir.resolve().relative_to(root.resolve()).as_posix()
        return HTTPStatus.CREATED, _json_bytes({"created": True, "path": rel}), "application/json; charset=utf-8"

    def handle_folder_rename(self, path: str, new_name: str) -> tuple[int, bytes, str]:
        if self._import is None:
            raise ValidationError("Import service is not enabled")
        result = self._import.rename_folder(path=path, new_name=new_name)
        if not result.get("updated"):
            raise NotFoundError(f"Folder not found: {path}")
        return HTTPStatus.OK, _json_bytes(result), "application/json; charset=utf-8"

    def handle_folder_delete(self, paths: list[Any], recursive: bool = True) -> tuple[int, bytes, str]:
        if self._import is None:
            raise ValidationError("Import service is not enabled")
        if not isinstance(paths, list):
            raise ValidationError("`paths` must be an array")
        if len(paths) == 0:
            raise ValidationError("`paths` must not be empty")

        results: list[dict[str, Any]] = []
        deleted = 0

        for raw_path in paths:
            if not isinstance(raw_path, str):
                results.append({
                    "path": str(raw_path),
                    "ok": False,
                    "error": "path must be a string",
                    "error_code": "VALIDATION_ERROR",
                })
                continue

            path = raw_path.strip()
            if not path:
                results.append({
                    "path": path,
                    "ok": False,
                    "error": "Missing folder path",
                    "error_code": "VALIDATION_ERROR",
                })
                continue

            try:
                detail = self._import.delete_folder(path=path, recursive=recursive)
                if detail.get("deleted"):
                    deleted += 1
                    results.append({"path": path, "ok": True, "detail": detail})
                else:
                    results.append({
                        "path": path,
                        "ok": False,
                        "error": f"Folder not found: {path}",
                        "error_code": "NOT_FOUND",
                    })
            except (ValidationError, NotFoundError, ConflictError) as e:
                item = {
                    "path": path,
                    "ok": False,
                    "error": str(e),
                    "error_code": getattr(e, "code", "VALIDATION_ERROR"),
                }
                details = getattr(e, "details", None)
                if details:
                    item["details"] = details
                results.append(item)
            except Exception as e:
                logger.exception("Folder delete failed", extra_fields={"path": path})
                results.append({
                    "path": path,
                    "ok": False,
                    "error": str(e),
                    "error_code": "INTERNAL_ERROR",
                })

        total = len(paths)
        payload = {
            "total": total,
            "deleted": deleted,
            "failed": total - deleted,
            "results": results,
        }
        return HTTPStatus.OK, _json_bytes(payload), "application/json; charset=utf-8"

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
        scale_str: str | None = None,
    ) -> tuple[int, bytes | Path, str]:
        """
        处理渲染请求

        GET /render/{pdf}/{page}.png
        """
        try:
            page = int(page_str.replace(".png", ""))
        except ValueError:
            raise NotFoundError("Invalid page number")

        try:
            scale = float((scale_str or "").strip() or "2.0")
        except ValueError:
            scale = 2.0

        # 渲染页面
        cache_path = self._render.render_page(pdf_name, page, scale=scale)

        return HTTPStatus.OK, cache_path, "image/png"

    def handle_pdf(
        self,
        pdf_name: str,
        range_header: str | None,
    ) -> tuple[int, bytes | Path | PdfRangePayload, str, dict[str, str]]:
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

                    return HTTPStatus.PARTIAL_CONTENT, PdfRangePayload(
                        path=pdf_path,
                        start=start,
                        end=end,
                        total_size=size,
                    ), content_type, {
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
        normalized_path = path.rstrip("/") if path != "/" else path

        if normalized_path == "/search":
            path = "/search.html"
        elif normalized_path == "/db":
            path = "/db.html"
        elif normalized_path == "/part":
            path = "/part.html"
        elif re.fullmatch(r"/part/\d+", normalized_path):
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
            if isinstance(error, UnauthorizedError):
                status = HTTPStatus.UNAUTHORIZED
            elif isinstance(error, ValidationError):
                status = HTTPStatus.BAD_REQUEST
            elif isinstance(error, NotFoundError):
                status = HTTPStatus.NOT_FOUND
            elif isinstance(error, ConflictError):
                status = HTTPStatus.CONFLICT
            elif isinstance(error, RateLimitError):
                status = HTTPStatus.TOO_MANY_REQUESTS
            elif isinstance(error, (DatabaseError, SearchError, RenderError)):
                status = HTTPStatus.INTERNAL_SERVER_ERROR
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

    def _normalize_relative_dir(
        self,
        path: str,
        *,
        allow_empty: bool,
        max_depth: int | None = None,
        field_name: str = "path",
    ) -> str:
        raw = (path or "").replace("\\", "/").strip().strip("/")
        if not raw:
            if allow_empty:
                return ""
            raise ValidationError("Missing path")
        parts = [p for p in raw.split("/") if p]
        if any(p in {".", ".."} for p in parts):
            raise ValidationError("Invalid path")
        if max_depth is not None and len(parts) > max_depth:
            raise ValidationError(
                f"Only top-level directory is supported for `{field_name}` (single-level policy)"
            )
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

    @staticmethod
    def _sanitize_document_payload(payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        clean = dict(payload)
        clean.pop("pdf_path", None)
        clean.pop("miner_dir", None)
        return clean
