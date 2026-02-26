"""
常量定义模块

定义系统中使用的所有常量，包括坐标系统、正则表达式、默认值等。
"""

from __future__ import annotations

import re

# ============================================================
# 版本信息
# ============================================================

VERSION = "2.0.0"

# ============================================================
# PDF 坐标系统 (厘米转换为点)
# ============================================================

PT_PER_CM = 72.0 / 2.54  # 1厘米 = 28.346点


def _pt(cm: float) -> float:
    """将厘米转换为PDF点"""
    return cm * PT_PER_CM


# 表格区域坐标 (厘米)
COORD_MARK_RECT = (_pt(17.5), _pt(25.8), _pt(18.5), _pt(26.2))  # 页脚标记区域
COORD_TABLE_RECT = (_pt(2.3), _pt(2.5), _pt(19.5), _pt(25.4))  # 表格区域

# 表格列坐标 (厘米)
COORD_COLS_X = {
    "fig_item": (_pt(2.3), _pt(3.8)),
    "part_number": (_pt(3.8), _pt(7.9)),
    "nomenclature": (_pt(7.9), _pt(16.3)),
    "effect": (_pt(16.3), _pt(18.4)),
    "units": (_pt(18.4), _pt(19.5)),
}

# ============================================================
# 正则表达式
# ============================================================

MONTHS = "(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
DATE_RE = re.compile(rf"\b{MONTHS}\s+\d{{1,2}}/\d{{2}}\b", re.I)
RF_TEXT_RE = re.compile(r"\bRF\s+\d{2}-\d{2}-\d{2}\b", re.I)
FIGURE_CODE_RE = re.compile(r"\b\d{2}-\d{2}-\d{2}-\d{2}[A-Z]?\b")
PAGE_TOKEN_RE = re.compile(r"\bPAGE\s+[0-9A-Z]+\b", re.I)
FIG_LINE_RE = re.compile(r"^FIG\.?\s+(.+)$", re.I)
FIGURE_LINE_RE = re.compile(r"^FIGURE\s+(.+)$", re.I)
ITEM_PN_SPLIT_RE = re.compile(r"^\s*(\d+[A-Z]?)\s+([A-Z0-9].+?)\s*$")
NOM_LEADING_DOTS_RE = re.compile(r"^\s*(\.+)\s*(.*)$", re.S)
PART_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-\./]*$")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# ============================================================
# HTTP 状态和响应
# ============================================================

HTTP_STATUS_OK = 200
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_TOO_MANY_REQUESTS = 429
HTTP_STATUS_INTERNAL_ERROR = 500

# ============================================================
# 缓存配置
# ============================================================

CACHE_STRATEGIES = {
    "search_results": {"ttl": 60, "max_size": 500},
    "part_detail": {"ttl": 300, "max_size": 1000},
    "render_image": {"ttl": 3600, "max_size": 100},
    "document_list": {"ttl": 600, "max_size": 10},
}

# ============================================================
# 搜索配置
# ============================================================

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
SEARCH_MODE_PART_NUMBER = "pn"
SEARCH_MODE_TERM = "term"
SEARCH_MODE_ALL = "all"

# 件号规范化相似度阈值
PN_SIMILARITY_THRESHOLD = 0.92

# ============================================================
# 数据库配置
# ============================================================

DB_BUSY_TIMEOUT_MS = 5000
DB_CACHE_SIZE = -20000  # 负数表示KB
DB_MMAP_SIZE = 268435456  # 256MB
METRICS_HISTOGRAM_WINDOW = 5000

# ============================================================
# API 路由
# ============================================================

ROUTE_API_SEARCH = "/api/search"
ROUTE_API_PART = "/api/part"
ROUTE_API_DOCS = "/api/docs"
ROUTE_API_HEALTH = "/api/health"
ROUTE_API_METRICS = "/api/metrics"
ROUTE_PDF = "/pdf"
ROUTE_RENDER = "/render"

# ============================================================
# 响应错误码
# ============================================================

ERROR_CODE_UNKNOWN = "UNKNOWN"
ERROR_CODE_DATABASE_ERROR = "DATABASE_ERROR"
ERROR_CODE_SEARCH_ERROR = "SEARCH_ERROR"
ERROR_CODE_RENDER_ERROR = "RENDER_ERROR"
ERROR_CODE_NOT_FOUND = "NOT_FOUND"
ERROR_CODE_INVALID_REQUEST = "INVALID_REQUEST"
ERROR_CODE_RATE_LIMITED = "RATE_LIMITED"
ERROR_CODE_INTERNAL = "INTERNAL_ERROR"
