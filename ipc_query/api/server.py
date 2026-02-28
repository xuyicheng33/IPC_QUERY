"""
HTTP服务器模块

提供HTTP服务器实现，处理请求路由和响应。
"""

from __future__ import annotations

import re
import sqlite3
import uuid
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote

from build_db import ensure_schema
from ..config import Config
from ..db.connection import Database
from ..db.repository import DocumentRepository, PartRepository
from ..exceptions import IpcQueryError, NotFoundError, ValidationError
from ..services.importer import ImportService
from ..services.render import RenderService, create_render_service
from ..services.scanner import ScanService
from ..services.search import SearchService, create_search_service
from ..utils.logger import get_logger
from .handlers import ApiHandlers

logger = get_logger(__name__)


def _json_bytes(obj: Any) -> bytes:
    """将对象转换为JSON字节"""
    import json
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _validated_content_length(content_length_raw: str | None, max_file_size_mb: int) -> int:
    """解析并校验上传请求体长度。"""
    raw = (content_length_raw or "").strip()
    try:
        content_length = int(raw or "0")
    except ValueError as e:
        raise ValidationError("Invalid Content-Length header") from e

    if content_length <= 0:
        raise ValidationError("Empty request body")

    max_body_bytes = max(1, int(max_file_size_mb)) * 1024 * 1024
    if content_length > max_body_bytes:
        raise ValidationError(f"File too large (max {max_file_size_mb}MB)")

    return content_length


def _display_host(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


class RequestHandler(BaseHTTPRequestHandler):
    """
    HTTP请求处理器

    处理所有HTTP请求，路由到对应的处理器方法。
    """

    def log_message(self, format: str, *args: object) -> None:
        """重写日志方法，使用自定义日志器"""
        logger.info(
            "HTTP request",
            extra_fields={
                "method": self.command,
                "path": self.path,
                "status": args[1] if len(args) > 1 else None,
            },
        )

    def _config(self) -> Config:
        config = getattr(self.server, "ipc_query_config", None)
        if isinstance(config, Config):
            return config
        raise RuntimeError("Request handler config is not initialized")

    def _handlers(self) -> ApiHandlers:
        handlers = getattr(self.server, "ipc_query_handlers", None)
        if isinstance(handlers, ApiHandlers):
            return handlers
        raise RuntimeError("Request handler API handlers are not initialized")

    def _send(
        self,
        status: int,
        body: bytes | Path,
        content_type: str,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        """发送响应"""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if isinstance(body, Path):
            self.send_header("Content-Length", str(body.stat().st_size))
        else:
            self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")

        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)

        self.end_headers()

        if isinstance(body, Path):
            # 发送文件
            with body.open("rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        else:
            self.wfile.write(body)

    def _send_json(self, status: int, obj: Any) -> None:
        """发送JSON响应"""
        self._send(status, _json_bytes(obj), "application/json; charset=utf-8")

    def _handle_error(self, error: Exception) -> None:
        """处理错误"""
        status, body, ct = self._handlers().handle_error(error)
        self._send(status, body, ct)

    def _cleanup_request_db(self) -> None:
        """请求结束后清理当前线程数据库连接。"""
        try:
            self._handlers()._db.close()
        except Exception:
            pass

    def _read_json_body(self, *, max_bytes: int = 64 * 1024) -> dict[str, Any]:
        content_length_raw = (self.headers.get("Content-Length") or "").strip()
        try:
            content_length = int(content_length_raw or "0")
        except ValueError as e:
            raise ValidationError("Invalid Content-Length header") from e
        if content_length <= 0:
            raise ValidationError("Empty request body")
        if content_length > max_bytes:
            raise ValidationError("JSON body too large")
        payload = self.rfile.read(content_length)
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except Exception as e:
            raise ValidationError("Invalid JSON body") from e
        if not isinstance(parsed, dict):
            raise ValidationError("JSON body must be an object")
        return parsed

    def do_GET(self) -> None:
        """处理GET请求"""
        try:
            path, _, query_string = self.path.partition("?")
            path = path or "/"

            # 路由匹配
            if path == "/api/search":
                status, search_body, ct = self._handlers().handle_search(query_string)
                self._send(status, search_body, ct)

            elif path.startswith("/api/part/"):
                part_id = path[len("/api/part/"):]
                status, part_body, ct = self._handlers().handle_part(part_id)
                self._send(status, part_body, ct)

            elif path == "/api/docs":
                status, docs_body, ct = self._handlers().handle_docs()
                self._send(status, docs_body, ct)

            elif path == "/api/docs/tree":
                qs = parse_qs(query_string) if query_string else {}
                rel_path = (qs.get("path") or [""])[0]
                status, body, ct = self._handlers().handle_docs_tree(path=rel_path)
                self._send(status, body, ct)

            elif path == "/api/health":
                status, health_body, ct = self._handlers().handle_health()
                self._send(status, health_body, ct)

            elif path == "/api/metrics":
                status, metrics_body, ct = self._handlers().handle_metrics()
                self._send(status, metrics_body, ct)

            elif path == "/api/capabilities":
                status, capabilities_body, ct = self._handlers().handle_capabilities()
                self._send(status, capabilities_body, ct)

            elif path == "/api/import/jobs":
                qs = parse_qs(query_string) if query_string else {}
                limit_raw = (qs.get("limit") or ["20"])[0]
                try:
                    limit = max(1, min(200, int(limit_raw)))
                except Exception:
                    limit = 20
                status, jobs_body, ct = self._handlers().handle_import_jobs(limit=limit)
                self._send(status, jobs_body, ct)

            elif path.startswith("/api/import/"):
                job_id = path[len("/api/import/") :]
                if not job_id:
                    raise NotFoundError("Missing import job id")
                status, job_body, ct = self._handlers().handle_import_job(job_id)
                self._send(status, job_body, ct)

            elif path.startswith("/api/scan/"):
                job_id = path[len("/api/scan/") :]
                if not job_id:
                    raise NotFoundError("Missing scan job id")
                status, job_body, ct = self._handlers().handle_scan_job(job_id)
                self._send(status, job_body, ct)

            elif path.startswith("/render/"):
                # /render/{pdf}/{page}.png
                match = re.match(r"^/render/([^/]+)/(\d+)\.png$", path)
                if match:
                    pdf_name_raw, page = match.groups()
                    pdf_name = unquote(pdf_name_raw)
                    qs = parse_qs(query_string) if query_string else {}
                    scale_raw = (qs.get("scale") or [""])[0]
                    status, render_body, ct = self._handlers().handle_render(pdf_name, page, scale_raw)
                    if isinstance(render_body, Path):
                        # 发送图片文件
                        self.send_response(status)
                        self.send_header("Content-Type", ct)
                        self.send_header("Content-Length", str(render_body.stat().st_size))
                        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                        self.end_headers()
                        with render_body.open("rb") as f:
                            while True:
                                chunk = f.read(64 * 1024)
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                    else:
                        self._send(status, render_body, ct)
                else:
                    raise NotFoundError("Invalid render path")

            elif path.startswith("/pdf/"):
                pdf_name = unquote(path[len("/pdf/"):])
                range_header = self.headers.get("Range")
                status, pdf_body, ct, extra = self._handlers().handle_pdf(pdf_name, range_header)
                if isinstance(pdf_body, Path):
                    # 发送PDF文件
                    size = pdf_body.stat().st_size
                    self.send_response(status)
                    self.send_header("Content-Type", ct)
                    self.send_header("Content-Length", str(size))
                    for k, v in extra.items():
                        self.send_header(k, v)
                    self.end_headers()
                    with pdf_body.open("rb") as f:
                        while True:
                            chunk = f.read(64 * 1024)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                else:
                    self._send(status, pdf_body, ct, extra)

            else:
                # 静态文件
                status, static_body, ct = self._handlers().handle_static(path)
                if isinstance(static_body, Path):
                    size = static_body.stat().st_size
                    self.send_response(status)
                    self.send_header("Content-Type", ct)
                    self.send_header("Content-Length", str(size))
                    if ct.startswith("image/"):
                        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                    else:
                        self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    with static_body.open("rb") as f:
                        while True:
                            chunk = f.read(64 * 1024)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                else:
                    self._send(status, static_body, ct)

        except IpcQueryError as e:
            self._handle_error(e)
        except BrokenPipeError:
            pass  # 客户端断开连接
        except Exception as e:
            self._handle_error(e)
        finally:
            self._cleanup_request_db()

    def do_POST(self) -> None:
        """处理POST请求"""
        try:
            path, _, query_string = self.path.partition("?")
            path = path or "/"

            if path == "/api/import":
                if not self._handlers().import_enabled():
                    raise ValidationError("Import service is not enabled")
                qs = parse_qs(query_string) if query_string else {}
                filename = (self.headers.get("X-File-Name") or (qs.get("filename") or [""])[0]).strip()
                target_dir = (self.headers.get("X-Target-Dir") or (qs.get("target_dir") or [""])[0]).strip()
                content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                content_length = _validated_content_length(
                    self.headers.get("Content-Length"),
                    self._config().import_max_file_size_mb,
                )
                payload = self.rfile.read(content_length)
                if len(payload) != content_length:
                    raise ValidationError("Incomplete request body")
                status, body, ct = self._handlers().handle_import_submit(
                    filename=filename,
                    payload=payload,
                    content_type=content_type,
                    target_dir=target_dir,
                )
                self._send(status, body, ct)
                return

            if path == "/api/docs/batch-delete":
                json_payload = self._read_json_body()
                raw_paths = json_payload.get("paths")
                if not isinstance(raw_paths, list):
                    raise ValidationError("`paths` must be an array")
                status, body, ct = self._handlers().handle_docs_batch_delete(paths=raw_paths)
                self._send(status, body, ct)
                return

            if path == "/api/docs/rename":
                json_payload = self._read_json_body()
                status, body, ct = self._handlers().handle_doc_rename(
                    path=str(json_payload.get("path") or ""),
                    new_name=str(json_payload.get("new_name") or ""),
                )
                self._send(status, body, ct)
                return

            if path == "/api/docs/move":
                json_payload = self._read_json_body()
                status, body, ct = self._handlers().handle_doc_move(
                    path=str(json_payload.get("path") or ""),
                    target_dir=str(json_payload.get("target_dir") or ""),
                )
                self._send(status, body, ct)
                return

            if path == "/api/folders":
                json_payload = self._read_json_body()
                parent_path = str(json_payload.get("path") or "")
                folder_name = str(json_payload.get("name") or "")
                status, body, ct = self._handlers().handle_folder_create(path=parent_path, name=folder_name)
                self._send(status, body, ct)
                return

            if path == "/api/scan":
                qs = parse_qs(query_string) if query_string else {}
                path_arg = (qs.get("path") or [""])[0]
                if not path_arg and (self.headers.get("Content-Length") or "").strip():
                    json_payload = self._read_json_body()
                    path_arg = str(json_payload.get("path") or "")
                status, body, ct = self._handlers().handle_scan_submit(path=path_arg)
                self._send(status, body, ct)
                return

            raise NotFoundError(f"Unsupported POST path: {path}")
        except IpcQueryError as e:
            self._handle_error(e)
        except BrokenPipeError:
            pass
        except Exception as e:
            self._handle_error(e)
        finally:
            self._cleanup_request_db()

    def do_DELETE(self) -> None:
        """处理DELETE请求"""
        try:
            path, _, query_string = self.path.partition("?")
            path = path or "/"

            if path == "/api/docs":
                qs = parse_qs(query_string) if query_string else {}
                pdf_name = (qs.get("name") or [""])[0].strip()
                status, body, ct = self._handlers().handle_doc_delete(pdf_name)
                self._send(status, body, ct)
                return

            if path.startswith("/api/docs/"):
                pdf_name = unquote(path[len("/api/docs/"):]).strip()
                status, body, ct = self._handlers().handle_doc_delete(pdf_name)
                self._send(status, body, ct)
                return

            raise NotFoundError(f"Unsupported DELETE path: {path}")
        except IpcQueryError as e:
            self._handle_error(e)
        except BrokenPipeError:
            pass
        except Exception as e:
            self._handle_error(e)
        finally:
            self._cleanup_request_db()

    def do_HEAD(self) -> None:
        """处理HEAD请求"""
        try:
            path, _, _ = self.path.partition("?")
            status, body, ct = self._handlers().handle_static(path)

            self.send_response(status)
            self.send_header("Content-Type", ct)
            if isinstance(body, Path):
                self.send_header("Content-Length", str(body.stat().st_size))
            else:
                self.send_header("Content-Length", str(len(body)))
            self.end_headers()

        except Exception:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
        finally:
            self._cleanup_request_db()


class Server:
    """
    HTTP服务器

    封装 ThreadingHTTPServer，提供启动和停止方法。
    """

    def __init__(
        self,
        config: Config,
        db: Database,
        search_service: SearchService,
        render_service: RenderService,
        import_service: ImportService | None,
        scan_service: ScanService | None,
        import_enabled: bool,
        scan_enabled: bool,
        import_reason: str,
        scan_reason: str,
    ):
        self._config = config
        self._db = db
        self._search = search_service
        self._render = render_service
        self._import = import_service
        self._scan = scan_service
        self._import_enabled = bool(import_enabled)
        self._scan_enabled = bool(scan_enabled)
        self._import_reason = str(import_reason or "")
        self._scan_reason = str(scan_reason or "")
        self._server: ThreadingHTTPServer | None = None

    def start(self) -> None:
        """启动服务器"""
        # 创建文档仓库
        doc_repo = DocumentRepository(self._db)

        api_handlers = ApiHandlers(
            search_service=self._search,
            render_service=self._render,
            doc_repo=doc_repo,
            db=self._db,
            config=self._config,
            import_service=self._import,
            scan_service=self._scan,
            import_enabled=self._import_enabled,
            scan_enabled=self._scan_enabled,
            import_reason=self._import_reason,
            scan_reason=self._scan_reason,
        )

        # 创建服务器
        self._server = ThreadingHTTPServer(
            (self._config.host, self._config.port),
            RequestHandler,
        )
        setattr(self._server, "ipc_query_config", self._config)
        setattr(self._server, "ipc_query_handlers", api_handlers)
        server_address = self._server.server_address
        if isinstance(server_address, tuple):
            host = _display_host(server_address[0])
            port = int(server_address[1])
        else:
            host = _display_host(server_address)
            port = int(self._config.port)

        logger.info(
            "Server started",
            extra_fields={
                "host": host,
                "port": int(port),
            },
        )

        print(f"Server running at http://{host}:{port}/")

        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        finally:
            self.stop()

    def stop(self) -> None:
        """停止服务器"""
        server = self._server
        self._server = None
        if server:
            try:
                server.shutdown()
            finally:
                server.server_close()
        if self._import is not None:
            self._import.stop()
        if self._scan is not None:
            self._scan.stop()
        self._db.close_all()
        logger.info("Server stopped")


def _is_database_writable(db_path: Path) -> bool:
    """检测数据库是否可写。"""
    if not db_path.exists():
        return True

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True, timeout=1.0)
    except sqlite3.Error:
        return False

    probe_name = f"__ipc_write_probe_{uuid.uuid4().hex}"
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(f"CREATE TABLE {probe_name}(id INTEGER)")
        conn.execute(f"DROP TABLE {probe_name}")
        conn.execute("ROLLBACK")
        return True
    except sqlite3.Error:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        return False
    finally:
        conn.close()


def _is_directory_writable(path: Path) -> bool:
    """检测目录是否可写。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    probe_path = path / f".__ipc_write_probe_{uuid.uuid4().hex}"
    try:
        probe_path.write_bytes(b"1")
        probe_path.unlink(missing_ok=True)
        return True
    except OSError:
        try:
            probe_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _resolve_import_enablement(config: Config) -> tuple[bool, dict[str, Any]]:
    mode = (config.import_mode or "auto").strip().lower()
    if mode not in {"auto", "enabled", "disabled"}:
        mode = "auto"
    if mode == "disabled":
        return False, {
            "mode": mode,
            "reason": "disabled_by_config",
        }

    db_writable = _is_database_writable(config.database_path)
    pdf_writable = _is_directory_writable(config.pdf_dir) if config.pdf_dir is not None else False
    upload_writable = _is_directory_writable(config.upload_dir)
    fs_writable = pdf_writable and upload_writable
    enabled = db_writable and fs_writable

    details = {
        "mode": mode,
        "db_writable": db_writable,
        "pdf_dir": str(config.pdf_dir) if config.pdf_dir is not None else None,
        "pdf_writable": pdf_writable,
        "upload_dir": str(config.upload_dir),
        "upload_writable": upload_writable,
    }
    if mode == "enabled" and not enabled:
        details["reason"] = "enabled_but_write_requirements_not_met"
    elif mode == "auto" and not enabled:
        details["reason"] = "auto_disabled_due_to_write_requirements"
    return enabled, details


def _enablement_reason_text(enabled: bool, details: dict[str, Any], *, mode_name: str) -> str:
    if enabled:
        return ""

    reason = str(details.get("reason") or "")
    mode = str(details.get("mode") or mode_name or "auto")
    db_writable = bool(details.get("db_writable"))
    pdf_writable = bool(details.get("pdf_writable"))
    upload_writable = bool(details.get("upload_writable"))

    if reason == "disabled_by_config":
        return f"{mode_name} service disabled by import_mode={mode}"
    if reason in {"enabled_but_write_requirements_not_met", "auto_disabled_due_to_write_requirements"}:
        return (
            f"{mode_name} service unavailable: "
            f"db_writable={db_writable}, pdf_writable={pdf_writable}, upload_writable={upload_writable}"
        )
    return f"{mode_name} service is not enabled"


def create_server(config: Config) -> Server:
    """
    创建服务器实例

    Args:
        config: 配置对象

    Returns:
        Server实例
    """
    if config.pdf_dir is None:
        config.pdf_dir = config.upload_dir
        config.pdf_dir.mkdir(parents=True, exist_ok=True)

    required_tables = {"documents", "pages", "parts", "xrefs", "aliases", "scan_state"}
    needs_schema_init = not config.database_path.exists()
    if not needs_schema_init:
        probe_db = Database(config.database_path, readonly=True)
        try:
            rows = probe_db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            table_names = {str(r["name"]) for r in rows}
            needs_schema_init = not required_tables.issubset(table_names)
        finally:
            probe_db.close_all()

    if needs_schema_init:
        rw_db = Database(config.database_path, readonly=False)
        try:
            with rw_db.connection() as conn:
                ensure_schema(conn)
        finally:
            rw_db.close_all()

    # 初始化只读数据库连接
    db = Database(config.database_path, readonly=True)

    # 创建仓库
    part_repo = PartRepository(db, config.pdf_dir)

    # 创建服务
    search_service = create_search_service(part_repo, config)
    render_service = create_render_service(config.pdf_dir, config.cache_dir, config)
    import_service: ImportService | None
    scan_service: ScanService | None

    def _on_content_changed() -> None:
        search_service.clear_cache()
        render_service.clear_cache()

    import_enabled, enablement_details = _resolve_import_enablement(config)
    if import_enabled:
        db_write_lock = threading.Lock()
        import_service = ImportService(
            db_path=config.database_path,
            pdf_dir=config.pdf_dir,
            upload_dir=config.upload_dir,
            max_file_size_mb=config.import_max_file_size_mb,
            queue_size=config.import_queue_size,
            job_timeout_s=config.import_job_timeout_s,
            max_jobs_retained=config.import_jobs_retained,
            on_success=_on_content_changed,
            db_write_lock=db_write_lock,
        )
        scan_service = ScanService(
            db_path=config.database_path,
            pdf_dir=config.pdf_dir,
            max_jobs_retained=config.import_jobs_retained,
            on_success=_on_content_changed,
            db_write_lock=db_write_lock,
        )
    else:
        import_service = None
        scan_service = None
        logger.warning(
            "Import service disabled",
            extra_fields=enablement_details,
        )

    scan_enabled = scan_service is not None
    import_reason = _enablement_reason_text(import_enabled, enablement_details, mode_name="import")
    scan_reason = "" if scan_enabled else _enablement_reason_text(scan_enabled, enablement_details, mode_name="scan")

    # 预热
    search_service.warmup()

    if scan_service is not None:
        try:
            scan_service.submit_scan("")
        except Exception:
            logger.exception("Failed to enqueue startup scan job")

    return Server(
        config,
        db,
        search_service,
        render_service,
        import_service,
        scan_service,
        import_enabled=import_enabled,
        scan_enabled=scan_enabled,
        import_reason=import_reason,
        scan_reason=scan_reason,
    )
