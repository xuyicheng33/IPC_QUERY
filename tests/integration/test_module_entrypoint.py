"""
模块入口点集成测试
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_python_m_ipc_query_propagates_exit_code(tmp_path: Path) -> None:
    missing_db = tmp_path / "missing.sqlite"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ipc_query",
            "query",
            "abc",
            "--db",
            str(missing_db),
        ],
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 2
    assert "Database not found" in proc.stdout
