# IPC_QUERY (v4.0.0)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)
[![CI](https://github.com/xuyicheng33/IPC_QUERY/actions/workflows/ci.yml/badge.svg)](https://github.com/xuyicheng33/IPC_QUERY/actions/workflows/ci.yml)

IPC_QUERY 是一个面向 IPC（Illustrated Parts Catalog）PDF 的工程化查询系统，覆盖“建库、检索、详情预览、文档运维”全链路能力，适用于企业客户件号检索、内部维保知识查询和轻量生产部署。

## 核心能力

- PDF 抽取建库：将 IPC PDF 解析并写入 SQLite。
- 多维搜索：支持按件号、术语、综合模式检索，并支持分页、排序与查询状态保持（搜索页与详情页切换后可恢复原筛选条件）。
- 零件详情：展示层级关系、来源文档、页码与关键元数据。
- 文档运维：`/db` 页面支持导入、删除、重命名、移动、目录管理与增量扫描。
- API 集成：对外提供稳定 HTTP API，便于前端或第三方系统接入。

## 技术架构

- 后端：Python 3.10+（标准库 HTTP Server + SQLite + PyMuPDF）
- 前端：React + TypeScript + Vite，构建产物输出到 `web/`
- 数据层：SQLite 单文件数据库（默认 `data/ipc.sqlite`）
- 运行模式：本地直接运行 / Docker Compose / 云服务器直连或反向代理部署

## 快速开始（本地）

### 1. 环境要求

- Python 3.10+
- Node.js 18+（推荐 20+）
- npm 9+

### 2. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
npm --prefix frontend install
```

### 3. 构建前端静态资源

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

### 4. 构建数据库（首次）

```bash
python3 -m ipc_query build \
  --pdf-dir ./data/pdfs \
  --output ./data/ipc.sqlite
```

### 5. 启动服务

```bash
python3 -m ipc_query serve \
  --db ./data/ipc.sqlite \
  --host 127.0.0.1 \
  --port 8791 \
  --pdf-dir ./data/pdfs \
  --upload-dir ./data/pdfs
```

访问：`http://127.0.0.1:8791`

## Docker 快速运行

```bash
docker compose up -d --build
```

默认端口 `8791`，容器健康检查接口为 `/api/health`。
如需自定义宿主机 PDF 目录，设置 `.env` 中 `PDF_HOST_DIR`（默认 `./data/pdfs`）。

## 云服务器部署

生产部署建议使用 Linux + Docker Compose。Nginx 与 HTTPS 在公网场景强烈建议启用，在内网场景可按需启用。

完整步骤见：[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

该文档包含：
- Docker Compose 生产部署（推荐）
- systemd 原生部署（备选）
- Nginx 反向代理与 TLS（按需）
- 备份、升级、回滚与排障

## API 概览

| Endpoint | Method | 说明 |
|---|---|---|
| `/api/search` | GET | 搜索零件 |
| `/api/part/{id}` | GET | 查询零件详情 |
| `/api/docs` | GET | 列出已入库文档 |
| `/api/docs/tree?path={dir}` | GET | 查询目录树与文件状态 |
| `/api/import` | POST | 上传 PDF 并创建导入任务 |
| `/api/import/jobs` | GET | 查询导入任务列表 |
| `/api/import/{job_id}` | GET | 查询导入任务状态 |
| `/api/docs?name={pdf_name}` | DELETE | 删除单个 PDF |
| `/api/docs/batch-delete` | POST | 批量删除 PDF |
| `/api/docs/rename` | POST | 重命名 PDF |
| `/api/docs/move` | POST | 移动 PDF |
| `/api/folders` | POST | 新建目录（canonical） |
| `/api/folders/rename` | POST | 重命名目录（canonical） |
| `/api/folders/delete` | POST | 删除目录（canonical） |
| `/api/docs/folder/create` | POST | 新建目录（legacy alias，计划于 2026-06-30 sunset） |
| `/api/docs/folder/rename` | POST | 重命名目录（legacy alias，计划于 2026-06-30 sunset） |
| `/api/docs/folder/delete` | POST | 删除目录（legacy alias，计划于 2026-06-30 sunset） |
| `/api/scan` | POST | 触发增量扫描 |
| `/api/scan/{job_id}` | GET | 查询扫描任务状态 |
| `/api/capabilities` | GET | 查询导入/扫描能力开关 |
| `/api/health` | GET | 健康检查 |
| `/api/metrics` | GET | 运行指标 |

## 关键配置项（环境变量）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_PATH` | `data/ipc.sqlite` | SQLite 文件路径 |
| `HOST` | `127.0.0.1` | 服务监听地址 |
| `PORT` | `8791` | 服务端口 |
| `PDF_DIR` | 空 | PDF 目录（不填时由 `UPLOAD_DIR` 或默认值兜底） |
| `UPLOAD_DIR` | 空 | 上传目录（未设置时默认跟随 `PDF_DIR`） |
| `IMPORT_MODE` | `auto` | `auto`/`enabled`/`disabled` |
| `CACHE_SIZE` | `1000` | 缓存条目上限 |
| `CACHE_TTL` | `300` | 搜索缓存 TTL（秒，`search_results` 与详情缓存均使用该值） |
| `RENDER_SEMAPHORE` | `4` | 渲染并发上限（canonical） |
| `RENDER_WORKERS` | `4` | `RENDER_SEMAPHORE` 的兼容别名（deprecated） |
| `WRITE_API_AUTH_MODE` | `disabled` | 写接口鉴权模式：`disabled` / `api_key` |
| `WRITE_API_KEY` | 空 | 当 `WRITE_API_AUTH_MODE=api_key` 时必填，请通过请求头 `X-API-Key` 传递 |
| `LEGACY_FOLDER_ROUTES_ENABLED` | `true` | 是否启用 `/api/docs/folder/*` legacy 路由 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_FORMAT` | `json` | `json` 或 `text` |

参考模板：`.env.example`

## 目录策略与鉴权说明

- 目录策略固定为 `single_level`：仅允许根目录和一级子目录，不支持多级目录写入。
- 当 `WRITE_API_AUTH_MODE=api_key` 时，所有写接口（导入/删除/改名/移动/建目录/删目录/扫描）必须携带 `X-API-Key`。
- 写接口鉴权失败返回 `401`，错误码为 `UNAUTHORIZED`。
- 运行时可通过 `/api/capabilities` 获取：
  - `write_auth_mode`
  - `write_auth_required`
  - `legacy_folder_routes_enabled`
  - `directory_policy`
  - `path_policy_warning_count`

## 质量门禁（建议提交前执行）

```bash
pytest
node --test tests/web/*.test.mjs
npm --prefix frontend run typecheck
npm --prefix frontend run build
python3 -m mypy ipc_query cli
python3 -m pip wheel . -w ./dist --no-deps
```

## 文档导航

- [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)：从零跑通项目
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)：云服务器部署手册
- [docs/MAINTENANCE.md](docs/MAINTENANCE.md)：维护与清理约定
- [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md)：发版检查清单
- [docs/STRUCTURE.md](docs/STRUCTURE.md)：目录结构规范
- [docs/frontend/FRONTEND_HANDOFF_V4.md](docs/frontend/FRONTEND_HANDOFF_V4.md)：前端交接说明

## 许可证

本项目使用 MIT License，详见 [LICENSE](LICENSE)。
