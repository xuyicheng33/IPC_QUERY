# 目录结构规范

## 一级目录职责

- `ipc_query/`：后端核心实现（API、服务、数据库、配置）
- `frontend/`：React + Vite 前端源码（开发入口）
- `web/`：前端构建产物（运行时静态资源）
- `tests/`：单元、集成与前端测试
- `scripts/`：QA 和工具脚本
- `data/fixtures/`：可提交的固定样本数据
- `docs/`：维护文档与历史归档
- `legacy/`：历史入口与历史资料（归档，不建议继续扩展）

## 根目录收敛原则

- 根目录只放工程入口和基础配置文件。
- 历史脚本不再平铺在根目录，统一放入 `legacy/` 或 `scripts/`。
- `build_db.py` 仅作为兼容壳入口，真实实现位于 `ipc_query/build_db.py`。

## docs 组织策略

- 日常文档：放在 `docs/` 根目录（如 `README.md`、`MAINTENANCE.md`、`STRUCTURE.md`）。
- 前端设计交接文档：放在 `docs/frontend/`。
- 历史过程文档：放入 `docs/archive/`（例如 UI 重建过程文档）。

## 新文件放置决策表

| 文件类型 | 建议位置 |
|---|---|
| 主服务代码 | `ipc_query/` |
| 前端页面与组件源码 | `frontend/` |
| 前端构建产物 | `web/` |
| QA 检查/生成脚本 | `scripts/qa/` |
| 工具脚本 | `scripts/tools/` |
| 历史/弃用入口 | `legacy/` |
| 版本管理样本 | `data/fixtures/` |
| 运行态临时产物 | `tmp/`（不提交） |
| 日常维护文档 | `docs/` |
| 前端设计交接文档 | `docs/frontend/` |
| 历史文档归档 | `docs/archive/` |
