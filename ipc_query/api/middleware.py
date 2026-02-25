"""
中间件模块

提供请求处理中间件，如日志、错误处理、CORS等。
"""

from __future__ import annotations

import time
from typing import Any, Callable

from ..utils.logger import get_logger

logger = get_logger(__name__)


class Middleware:
    """中间件基类"""

    def __init__(self, next_handler: Callable | None = None):
        self._next = next_handler

    def __call__(self, *args, **kwargs) -> Any:
        if self._next:
            return self._next(*args, **kwargs)
        return None


class LoggingMiddleware(Middleware):
    """
    日志中间件

    记录请求信息和响应时间。
    """

    def __call__(self, method: str, path: str, *args, **kwargs) -> Any:
        start_time = time.perf_counter()

        logger.info(
            "Request started",
            extra_fields={"method": method, "path": path},
        )

        try:
            result = super().__call__(*args, **kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "Request completed",
                extra_fields={
                    "method": method,
                    "path": path,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.error(
                "Request failed",
                extra_fields={
                    "method": method,
                    "path": path,
                    "duration_ms": round(duration_ms, 2),
                    "error": str(e),
                },
            )
            raise


class CORSMiddleware(Middleware):
    """
    CORS中间件

    添加跨域请求支持。
    """

    def __init__(
        self,
        next_handler: Callable | None = None,
        allow_origins: str = "*",
        allow_methods: str = "GET, POST, PUT, DELETE, OPTIONS",
        allow_headers: str = "Content-Type, Authorization",
    ):
        super().__init__(next_handler)
        self._allow_origins = allow_origins
        self._allow_methods = allow_methods
        self._allow_headers = allow_headers

    def get_headers(self) -> dict[str, str]:
        """获取CORS头"""
        return {
            "Access-Control-Allow-Origin": self._allow_origins,
            "Access-Control-Allow-Methods": self._allow_methods,
            "Access-Control-Allow-Headers": self._allow_headers,
        }


class RateLimitMiddleware(Middleware):
    """
    请求频率限制中间件

    限制请求频率以防止滥用。
    """

    def __init__(
        self,
        next_handler: Callable | None = None,
        requests_per_minute: int = 60,
        burst: int = 10,
    ):
        super().__init__(next_handler)
        self._rpm = requests_per_minute
        self._burst = burst
        self._requests: dict[str, list[float]] = {}
        # Note: In production, use a proper rate limiting solution like Redis

    def _is_allowed(self, client_id: str) -> bool:
        """检查是否允许请求"""
        import time
        now = time.time()
        minute_ago = now - 60

        # 获取客户端请求记录
        requests = self._requests.get(client_id, [])
        # 过滤掉一分钟前的请求
        requests = [t for t in requests if t > minute_ago]

        # 检查是否超过限制
        if len(requests) >= self._rpm:
            return False

        # 记录本次请求
        requests.append(now)
        self._requests[client_id] = requests

        return True
