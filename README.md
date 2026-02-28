# IPC_QUERY（v4.0.0）

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](https://opensource.org/licenses/MIT)

IPC_QUERY 是一个面向 IPC（Illustrated Parts Catalog）PDF 的零件查询系统，提供：

- PDF 数据抽取与 SQLite 建库
- Web 端检索（件号 / 术语 / 详情 / 层级关系）
- `/db` 页面文件管理（导入、删除、改名、移动、扫描）
- 后端 API（供前端或其他系统二次集成）

---

## 1. 你明天要演示：最快启动方式

### 1.1 环境要求

- Python 3.10+
- Node.js 18+（推荐 20+）
- npm 9+

### 1.2 一次性安装依赖

```bash
# 在项目根目录执行
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"

# 前端依赖
npm --prefix frontend install
```

### 1.3 构建前端静态资源

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

前端构建产物会输出到 `web/`，由 Python 服务直接托管。

### 1.4 准备数据库（第一次需要）

```bash
# 方式 A：从你的 PDF 目录构建
python3 -m ipc_query build --pdf-dir ./data/pdfs --output ./data/ipc.sqlite

# 方式 B：如果仓库里已有可用 data/ipc.sqlite，可跳过构建
```

### 1.5 启动服务

```bash
python3 -m ipc_query serve \
  --db ./data/ipc.sqlite \
  --host 127.0.0.1 \
  --port 8791 \
  --pdf-dir ./data/pdfs \
  --upload-dir ./data/pdfs
```

浏览器打开：`http://127.0.0.1:8791`

---

## 2. 页面与路由说明

- `/`：首页（快速查询入口）
- `/search`：搜索页（件号 / 术语 / 分页 / 排序）
- `/part/{id}`：零件详情（来源、页脚元数据、术语高亮、层级关系、页预览）
- `/db`：文档管理页（目录与 PDF 管理）

> 说明：旧版 `/viewer.html` 已下线，统一使用浏览器原生 PDF 查看路径 `/pdf/{relative_path}#page={n}`。

---

## 3. API 一览

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/search` | GET | 搜索零件 |
| `/api/part/{id}` | GET | 获取零件详情 |
| `/api/docs` | GET | 列出已入库文档 |
| `/api/docs/tree?path={dir}` | GET | 查询目录树及文件状态 |
| `/api/import` | POST | 上传 PDF（创建导入任务） |
| `/api/import/jobs` | GET | 查询导入任务列表 |
| `/api/import/{job_id}` | GET | 查询导入任务状态 |
| `/api/docs?name={pdf_name}` | DELETE | 删除单个 PDF |
| `/api/docs/batch-delete` | POST | 批量删除 PDF |
| `/api/docs/rename` | POST | 重命名 PDF |
| `/api/docs/move` | POST | 移动 PDF |
| `/api/docs/folder/create` | POST | 新建目录 |
| `/api/docs/folder/rename` | POST | 重命名目录 |
| `/api/docs/folder/delete` | POST | 删除目录 |
| `/api/scan` | POST | 触发增量扫描 |
| `/api/scan/{job_id}` | GET | 查询扫描任务状态 |
| `/api/capabilities` | GET | 前端能力开关（导入/扫描可用性） |
| `/api/health` | GET | 健康检查 |
| `/api/metrics` | GET | 运行指标 |

`/api/part/{id}` 中 `part` 对象包含以下页脚元字段（可为空）：

- `figure_label`
- `date_text`
- `page_token`
- `rf_text`

---

## 4. 常用开发命令

```bash
# 后端测试
pytest

# 前端纯逻辑测试
node --test tests/web/*.test.mjs

# 前端类型与构建
npm --prefix frontend run typecheck
npm --prefix frontend run build

# Python 包打包（wheel）
python3 -m pip wheel . -w ./dist --no-deps
```

---

## 5. Docker 运行（可选）

```bash
docker compose up --build
```

默认端口：`8791`。  
需要让容器可写导入时，请确保挂载目录具备写权限并配置 `IMPORT_MODE=enabled` 或 `auto`。

---

## 6. 仓库结构（简版）

```text
ipc_query/      # 后端核心（api/services/db/config）
frontend/       # React + Vite 源码
web/            # 前端构建产物（运行时静态资源）
tests/          # 单元/集成/前端测试
scripts/        # QA/工具脚本
docs/           # 项目文档
```

更多文档见：`docs/README.md`。

---

## 7. v4.0 发布流程（建议）

```bash
git checkout main
git pull --ff-only

# 质量门禁
pytest
node --test tests/web/*.test.mjs
npm --prefix frontend run typecheck
npm --prefix frontend run build

# 版本标签
git tag -a v4.0.0 -m "Release v4.0.0"
git push origin main
git push origin v4.0.0
```

然后在 GitHub Releases 基于 `v4.0.0` 创建 release（标题可写 `v4.0`）。
