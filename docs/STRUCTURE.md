# 目录结构规范（v4.0）

## 一级目录职责

- `ipc_query/`：后端核心实现（API、服务、数据库、配置）
- `frontend/`：React + Vite 前端源码（开发态）
- `web/`：前端构建产物（运行态静态资源）
- `tests/`：单元、集成与前端测试
- `scripts/`：QA 与工具脚本
- `data/fixtures/`：可提交的固定样本数据
- `docs/`：当前维护文档
- `.github/workflows/`：CI 工作流
- `LICENSE`：开源许可证文本

## 根目录收敛原则

- 根目录只保留工程入口与配置文件。
- 临时实验脚本不直接落在根目录，统一收敛到 `scripts/`。
- `build_db.py` 只做兼容入口，真实实现位于 `ipc_query/build_db.py`。

## docs 组织策略

- 核心文档：`docs/README.md`、`docs/GETTING_STARTED.md`、`docs/MAINTENANCE.md`、`docs/RELEASE_CHECKLIST.md`。
- 前端交接文档：`docs/frontend/`。
- 保持“只维护当前版本文档”，过时文档及时删除，避免信息冲突。

## 新文件放置决策表

| 文件类型 | 建议位置 |
|---|---|
| 主服务代码 | `ipc_query/` |
| 前端页面与组件源码 | `frontend/` |
| 前端构建产物 | `web/` |
| QA 检查/生成脚本 | `scripts/qa/` |
| 工具脚本 | `scripts/tools/` |
| 版本管理样本 | `data/fixtures/` |
| 运行态临时产物 | `tmp/`（不提交） |
| 日常维护文档 | `docs/` |
| 前端交接文档 | `docs/frontend/` |
