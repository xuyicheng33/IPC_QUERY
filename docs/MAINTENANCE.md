# 维护与清理规则

## 不应提交的文件

- Python 缓存：`__pycache__/`、`*.pyc`
- 测试/类型缓存：`.pytest_cache/`、`.mypy_cache/`
- 覆盖率文件：`.coverage*`
- 本地运行临时目录：`tmp/`
- SQLite 运行侧文件：`*.sqlite-wal`、`*.sqlite-shm`
- 本地运行数据：`data/ipc.sqlite`、`data/pdfs/`、`data/uploads/`
- 本地 Agent/IDE 个性化配置：`.claude/`、`.vscode/`（如存在）

## 日常维护约定

- 新功能优先扩展 `ipc_query/`、`frontend/`、`tests/`。
- 历史入口只归档到 `legacy/`，不在其上继续叠加新逻辑。
- `web/` 为前端构建产物；改动前端源码后应重新构建并更新该目录。

## 文档维护约定

- `README.md` 保持“新用户 1 分钟能启动”。
- `docs/README.md` 维护文档入口。
- 前端布局/交互变更后，同步更新设计交接文档（`docs/frontend/*`）。
- 历史过程文档统一放入 `docs/archive/`，避免干扰主文档。

## 提交前最小检查清单

```bash
# 1) 工作区检查
git status

# 2) 运行测试
pytest
node --test tests/web/*.test.mjs

# 3) 类型检查（可选但建议）
mypy ipc_query cli
mypy scripts
```

## 发布检查清单

```bash
# 1) 确认在 main 且已同步远端
git checkout main
git pull --ff-only

# 2) 打版本标签（示例）
git tag -a release3 -m "Release release3 (v3.0.0)"

# 3) 推送
git push origin main
git push origin release3
```

然后在 GitHub Releases 页面基于对应 tag 发布 release。
