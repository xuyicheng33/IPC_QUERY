# 维护与清理规则

## 必须遵守的提交规则

不要提交以下运行态文件：

- Python 缓存：`__pycache__/`、`*.pyc`
- 测试缓存：`.pytest_cache/`
- 类型检查缓存：`.mypy_cache/`
- 覆盖率文件：`.coverage*`
- 临时目录：`tmp/`
- SQLite 运行侧文件：`*.sqlite-wal`、`*.sqlite-shm`
- 本地运行数据：`data/pdfs/`、`data/uploads/`、`data/ipc.sqlite`

## QA 样本维护流程

1. 稳定样本放入 `data/fixtures/qa/baseline/`。
2. 自动扫描或实验样本放入 `data/fixtures/qa/archive/`。
3. 只有长期回归需要时，才从 `archive` 提升到 `baseline`。

## 脚本维护策略

- 日常可执行脚本统一放在 `scripts/`。
- 历史入口或弃用脚本放入 `legacy/`。
- 根目录只保留必要入口（当前仅保留 `build_db.py` 兼容壳）。

## 每次整理后的最小检查清单

```bash
# 1) 不应有被跟踪的 pycache/pyc
git ls-files | rg "__pycache__|\\.pyc$"

# 2) 文档不应包含过时 demo 默认路径
rg -n "demo_coords/" README.md docs scripts

# 3) 主要入口可运行
python3 build_db.py --help
python3 -m ipc_query --help
python3 scripts/tools/query_db.py --help
python3 legacy/web_server.py --help

# 4) 自动化测试
pytest
```
