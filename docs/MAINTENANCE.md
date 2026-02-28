# 维护与清理规则（v4.0）

## 不应提交的文件

- Python 缓存：`__pycache__/`、`*.pyc`
- 测试/类型缓存：`.pytest_cache/`、`.mypy_cache/`
- 覆盖率文件：`.coverage*`
- 本地运行临时目录：`tmp/`
- SQLite 运行侧文件：`*.sqlite-wal`、`*.sqlite-shm`
- 本地运行数据：`data/ipc.sqlite`、`data/pdfs/`、`data/uploads/`
- 本地 Agent/IDE 个性化配置：`.claude/`、`.vscode/`

## 日常维护约定

- 新功能优先放在 `ipc_query/`、`frontend/`、`tests/`、`docs/`。
- 兼容入口 `build_db.py` 只作为壳入口，真实逻辑放在 `ipc_query/build_db.py`。
- 改动前端源码后必须重新构建并更新 `web/`。
- 文档必须与当前行为一致，尤其是路由/API 合同。

## 文档维护约定

- `README.md`：确保新同学 10 分钟内可跑通系统。
- `docs/README.md`：维护文档入口，不保留失效链接。
- 前端行为变化后，同步更新 `docs/frontend/FRONTEND_HANDOFF_V4.md`。
- 每次版本发布前，更新 `docs/RELEASE_CHECKLIST.md` 的版本区段。

## 建议清理命令（本地）

```bash
rm -rf __pycache__ .pytest_cache .mypy_cache tmp
rm -f .coverage .coverage.*
find . -name "*.sqlite-wal" -o -name "*.sqlite-shm"
```

## 提交前最小检查清单

```bash
# 1) 工作区检查
git status

# 2) 后端测试
pytest

# 3) 前端测试
node --test tests/web/*.test.mjs

# 4) 前端类型与构建
npm --prefix frontend run typecheck
npm --prefix frontend run build
```
