"""
PDF渲染服务模块

提供PDF页面渲染为图片的功能。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, cast

import fitz  # PyMuPDF

from ..config import Config
from ..exceptions import PdfNotFoundError, PageNotFoundError, RenderError
from ..utils.logger import get_logger
from ..utils.metrics import metrics
from .cache import get_cache

logger = get_logger(__name__)


class RenderService:
    """
    PDF渲染服务

    提供PDF页面渲染功能，支持缩放和缓存。
    """

    def __init__(
        self,
        pdf_dir: Path | None,
        cache_dir: Path,
        config: Config,
    ):
        """
        初始化渲染服务

        Args:
            pdf_dir: PDF文件目录
            cache_dir: 缓存目录
            config: 配置对象
        """
        self._pdf_dir = pdf_dir
        self._cache_dir = cache_dir
        self._config = config
        self._cache = get_cache("render_image")
        self._semaphore = threading.BoundedSemaphore(config.render_semaphore)
        self._pdf_handles: dict[str, fitz.Document] = {}
        self._lock = threading.Lock()

        # 确保缓存目录存在
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Render service initialized",
            extra_fields={
                "pdf_dir": str(pdf_dir) if pdf_dir else None,
                "cache_dir": str(cache_dir),
                "max_workers": config.render_semaphore,
            },
        )

    def render_page(
        self,
        pdf_name: str,
        page: int,
        scale: float = 2.0,
    ) -> Path:
        """
        渲染PDF页面为图片

        Args:
            pdf_name: PDF文件名
            page: 页码（1-based）
            scale: 缩放比例

        Returns:
            渲染后的图片路径

        Raises:
            PdfNotFoundError: PDF文件不存在
            PageNotFoundError: 页面不存在
            RenderError: 渲染失败
        """
        # 参数验证
        page = max(1, page)
        scale = max(0.5, min(scale, 4.0))

        # 构建缓存文件路径
        cache_filename = f"{pdf_name}_{page}_{scale:.1f}.png"
        cache_path = self._cache_dir / cache_filename

        # 检查缓存文件
        if cache_path.exists():
            logger.debug(
                "Render cache hit",
                extra_fields={"pdf": pdf_name, "page": page},
            )
            return cache_path

        # 获取信号量
        acquired = self._semaphore.acquire(timeout=self._config.render_timeout)
        if not acquired:
            raise RenderError(
                "Render timeout - too many concurrent requests",
                details={"pdf": pdf_name, "page": page},
            )

        try:
            return self._do_render(pdf_name, page, scale, cache_path)
        finally:
            self._semaphore.release()

    def _do_render(
        self,
        pdf_name: str,
        page: int,
        scale: float,
        cache_path: Path,
    ) -> Path:
        """执行渲染"""
        start_time = time.perf_counter()

        # 查找PDF文件
        pdf_path = self._find_pdf(pdf_name)
        if pdf_path is None:
            raise PdfNotFoundError(pdf_name)

        try:
            # 打开PDF
            doc = cast(Any, fitz.open(str(pdf_path)))

            # 检查页码
            if page > doc.page_count:
                doc.close()
                raise PageNotFoundError(pdf_name, page)

            # 渲染页面
            page_obj = doc[page - 1]
            mat = fitz.Matrix(scale, scale)
            pix = page_obj.get_pixmap(matrix=mat)

            # 保存图片
            pix.save(str(cache_path))
            doc.close()

            duration_ms = (time.perf_counter() - start_time) * 1000
            metrics.record_render(duration_ms)

            logger.info(
                "Page rendered",
                extra_fields={
                    "pdf": pdf_name,
                    "page": page,
                    "scale": scale,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return cache_path

        except (PdfNotFoundError, PageNotFoundError):
            raise
        except Exception as e:
            logger.error(
                "Render failed",
                extra_fields={
                    "pdf": pdf_name,
                    "page": page,
                    "error": str(e),
                },
            )
            raise RenderError(
                f"Failed to render page: {e}",
                details={"pdf": pdf_name, "page": page},
            ) from e

    def _find_pdf(self, pdf_name: str) -> Path | None:
        """查找PDF文件"""
        # 安全处理文件名
        safe_name = pdf_name.replace("\\", "/").split("/")[-1]

        # 在 pdf_dir 中查找
        if self._pdf_dir:
            candidate = self._pdf_dir / safe_name
            if candidate.exists():
                return candidate

        # 尝试当前目录
        candidate = Path(safe_name)
        if candidate.exists():
            return candidate

        return None

    def get_page_count(self, pdf_name: str) -> int:
        """
        获取PDF页数

        Args:
            pdf_name: PDF文件名

        Returns:
            页数
        """
        pdf_path = self._find_pdf(pdf_name)
        if pdf_path is None:
            return 0

        try:
            doc = cast(Any, fitz.open(str(pdf_path)))
            count = int(doc.page_count)
            doc.close()
            return count
        except Exception:
            return 0

    def clear_cache(self) -> int:
        """
        清除渲染缓存

        Returns:
            删除的文件数
        """
        count = 0
        try:
            for f in self._cache_dir.glob("*.png"):
                f.unlink()
                count += 1
            logger.info("Render cache cleared", extra_fields={"count": count})
        except Exception as e:
            logger.error(
                "Failed to clear render cache",
                extra_fields={"error": str(e)},
            )
        return count


def create_render_service(
    pdf_dir: Path | None,
    cache_dir: Path,
    config: Config,
) -> RenderService:
    """创建渲染服务实例"""
    return RenderService(pdf_dir, cache_dir, config)
