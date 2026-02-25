"""
HTTP服务器模块

提供HTTP服务器实现，处理请求路由和响应。
"""

from __future__ import annotations

import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..config import Config
from ..db.connection import Database
from ..db.repository import DocumentRepository, PartRepository
from ..exceptions import IpcQueryError, NotFoundError
from ..services.render import RenderService, create_render_service
from ..services.search import SearchService, create_search_service
from ..utils.logger import get_logger
from .handlers import ApiHandlers

logger = get_logger(__name__)


def _json_bytes(obj: Any) -> bytes:
    """将对象转换为JSON字节"""
    import json
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class RequestHandler(BaseHTTPRequestHandler):
    """
    HTTP请求处理器

    处理所有HTTP请求，路由到对应的处理器方法。
    """

    # 类级别配置，在创建服务器时设置
    config: Config
    handlers: ApiHandlers

    def log_message(self, format: str, *args) -> None:
        """重写日志方法，使用自定义日志器"""
        logger.info(
            "HTTP request",
            extra_fields={
                "method": self.command,
                "path": self.path,
                "status": args[1] if len(args) > 1 else None,
            },
        )

    def _send(self, status: int, body: bytes, content_type: str, extra_headers: dict | None = None) -> None:
        """发送响应"""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
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
        status, body, ct = self.handlers.handle_error(error)
        self._send(status, body, ct)

    def do_GET(self) -> None:
        """处理GET请求"""
        try:
            path, _, query_string = self.path.partition("?")
            path = path or "/"

            # 路由匹配
            if path == "/api/search":
                status, body, ct = self.handlers.handle_search(query_string)
                self._send(status, body, ct)

            elif path.startswith("/api/part/"):
                part_id = path[len("/api/part/"):]
                status, body, ct = self.handlers.handle_part(part_id)
                self._send(status, body, ct)

            elif path == "/api/docs":
                status, body, ct = self.handlers.handle_docs()
                self._send(status, body, ct)

            elif path == "/api/health":
                status, body, ct = self.handlers.handle_health()
                self._send(status, body, ct)

            elif path == "/api/metrics":
                status, body, ct = self.handlers.handle_metrics()
                self._send(status, body, ct)

            elif path.startswith("/render/"):
                # /render/{pdf}/{page}.png
                match = re.match(r"^/render/([^/]+)/(\d+)\.png$", path)
                if match:
                    pdf_name, page = match.groups()
                    status, body, ct = self.handlers.handle_render(pdf_name, page)
                    if isinstance(body, Path):
                        # 发送图片文件
                        self.send_response(status)
                        self.send_header("Content-Type", ct)
                        self.send_header("Content-Length", str(body.stat().st_size))
                        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                        self.end_headers()
                        with body.open("rb") as f:
                            while True:
                                chunk = f.read(64 * 1024)
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                    else:
                        self._send(status, body, ct)
                else:
                    raise NotFoundError("Invalid render path")

            elif path.startswith("/pdf/"):
                pdf_name = path[len("/pdf/"):]
                range_header = self.headers.get("Range")
                status, body, ct, extra = self.handlers.handle_pdf(pdf_name, range_header)
                if isinstance(body, Path):
                    # 发送PDF文件
                    size = body.stat().st_size
                    self.send_response(status)
                    self.send_header("Content-Type", ct)
                    self.send_header("Content-Length", str(size))
                    for k, v in extra.items():
                        self.send_header(k, v)
                    self.end_headers()
                    with body.open("rb") as f:
                        while True:
                            chunk = f.read(64 * 1024)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                else:
                    self._send(status, body, ct, extra)

            else:
                # 静态文件
                status, body, ct = self.handlers.handle_static(path)
                if isinstance(body, Path):
                    ct = mimetypes.guess_type(str(body))[0] or "application/octet-stream"
                    size = body.stat().st_size
                    self.send_response(status)
                    self.send_header("Content-Type", ct)
                    self.send_header("Content-Length", str(size))
                    if ct.startswith("image/"):
                        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                    else:
                        self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    with body.open("rb") as f:
                        while True:
                            chunk = f.read(64 * 1024)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                else:
                    self._send(status, body, ct)

        except IpcQueryError as e:
            self._handle_error(e)
        except BrokenPipeError:
            pass  # 客户端断开连接
        except Exception as e:
            self._handle_error(e)

    def do_HEAD(self) -> None:
        """处理HEAD请求"""
        try:
            path, _, _ = self.path.partition("?")
            status, body, ct = self.handlers.handle_static(path)

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
    ):
        self._config = config
        self._db = db
        self._search = search_service
        self._render = render_service
        self._server: ThreadingHTTPServer | None = None

    def start(self) -> None:
        """启动服务器"""
        # 创建文档仓库
        doc_repo = DocumentRepository(self._db)

        # 配置请求处理器
        RequestHandler.config = self._config
        RequestHandler.handlers = ApiHandlers(
            search_service=self._search,
            render_service=self._render,
            doc_repo=doc_repo,
            db=self._db,
            config=self._config,
        )

        # 创建服务器
        self._server = ThreadingHTTPServer(
            (self._config.host, self._config.port),
            RequestHandler,
        )

        logger.info(
            "Server started",
            extra_fields={
                "host": self._config.host,
                "port": self._config.port,
            },
        )

        print(f"Server running at http://{self._config.host}:{self._config.port}/")

        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        finally:
            self.stop()

    def stop(self) -> None:
        """停止服务器"""
        if self._server:
            self._server.shutdown()
            self._server = None
            logger.info("Server stopped")


def create_server(config: Config) -> Server:
    """
    创建服务器实例

    Args:
        config: 配置对象

    Returns:
        Server实例
    """
    # 初始化数据库
    db = Database(config.database_path, readonly=True)

    # 优化数据库（创建索引等）
    db.optimize()

    # 创建仓库
    part_repo = PartRepository(db, config.pdf_dir)

    # 创建服务
    search_service = create_search_service(part_repo, config)
    render_service = create_render_service(config.pdf_dir, config.cache_dir, config)

    # 预热
    search_service.warmup()

    return Server(config, db, search_service, render_service)
