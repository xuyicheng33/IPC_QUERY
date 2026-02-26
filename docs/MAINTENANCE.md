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

1. 新增稳定样本放入 `data/fixtures/qa/baseline/`。
2. 自动扫描或实验样本放入 `data/fixtures/qa/archive/`。
3. 只有在样本被验证为长期回归基线时，才从 `archive` 提升到 `baseline`。

## 兼容脚本策略

- 根目录脚本保留用于兼容旧命令。
- 实际逻辑放在 `scripts/` 下维护。
- 新增脚本时优先放到 `scripts/`，若需要兼容再增加根目录薄包装。

## 每次整理后的最小检查清单

```bash
# 1) 不应再有被跟踪的 pycache/pyc
git ls-files | rg "__pycache__|\\.pyc$"

# 2) 文档不应把历史 demo 路径当默认路径
rg -n "legacy demo|历史 demo|默认路径" README.md docs

# 3) 兼容入口可运行
python3 query_db.py --help
python3 qa_check.py --help
python3 web_server.py --help
python3 -m ipc_query --help

# 4) 自动化测试
pytest
```
