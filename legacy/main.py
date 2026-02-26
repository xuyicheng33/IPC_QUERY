#!/usr/bin/env python3
"""
IPC_QUERY - 航空零件目录查询系统

一个从 IPC (Illustrated Parts Catalog) PDF 文档中提取零件信息并提供查询服务的生产级系统。

用法:
    python -m ipc_query serve --db data/ipc.sqlite --port 8791
    python -m ipc_query build --pdf-dir ./pdfs --output data/ipc.sqlite
    python -m ipc_query query "113A4200-2" --db data/ipc.sqlite
"""

from __future__ import annotations

import sys

from cli.commands import main

if __name__ == "__main__":
    sys.exit(main())
