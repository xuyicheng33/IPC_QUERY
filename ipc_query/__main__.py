"""
IPC_QUERY 包入口点

支持 python -m ipc_query 方式运行。
"""

import sys

from cli.commands import main

if __name__ == "__main__":
    sys.exit(main())
