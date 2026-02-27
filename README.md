# IPC_QUERY

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](https://opensource.org/licenses/MIT)

IPC_QUERY 是一个面向 IPC (Illustrated Parts Catalog) PDF 的零件查询系统：
- 从 PDF 提取零件、层级与交叉引用信息
- 提供 Web 页面和 API 查询
- 支持在 `/db` 页面上传、删除、重扫 PDF

## 1 分钟上手

```bash
# 1) 安装
pip install -e .

# 2) 启动服务（默认使用 data/ipc.sqlite）
python3 -m ipc_query serve --db ./data/ipc.sqlite --port 8791

# 3) 打开
# http://127.0.0.1:8791
```

常用页面：
- `/`：首页
- `/search`：搜索页（件号/术语/来源过滤）
- `/part/{id}`：零件详情页（层级关系、xref、页预览）
- `/db`：PDF 文件管理页（上传、删除、重扫、目录管理）

## 常用操作

### 构建数据库

```bash
# 推荐入口
python3 -m ipc_query build --pdf-dir ./pdfs --output ./data/ipc.sqlite

# 兼容入口（壳文件）
python3 build_db.py --output ./data/ipc.sqlite
```

### 运行测试

```bash
pytest
node --test tests/web/*.test.mjs
```

### 前端构建（React + Vite）

```bash
cd frontend
npm install
npm run typecheck
npm run build
```

说明：前端产物输出到 `web/`，由 Python 服务继续托管。

## API 概览

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/search` | GET | 搜索零件 |
| `/api/part/{id}` | GET | 获取零件详情 |
| `/api/docs` | GET | 列出文档 |
| `/api/docs/tree?path={dir}` | GET | 目录树 + 文件状态 |
| `/api/import` | POST | 上传 PDF（创建导入任务） |
| `/api/import/jobs` | GET | 查询导入任务列表 |
| `/api/import/{job_id}` | GET | 查询导入任务状态 |
| `/api/docs?name={pdf_name}` | DELETE | 删除单个 PDF |
| `/api/docs/batch-delete` | POST | 批量删除 PDF |
| `/api/scan` | POST | 触发增量重扫 |
| `/api/scan/{job_id}` | GET | 查询重扫状态 |
| `/api/health` | GET | 健康检查 |
| `/api/metrics` | GET | 运行指标 |

## 仓库结构（简版）

```text
ipc_query/      # 后端核心（api/services/db/config）
frontend/       # React + Vite 源码
web/            # 前端构建产物（服务静态托管）
tests/          # 单元/集成/前端测试
scripts/        # QA 与工具脚本
docs/           # 文档（维护规范、结构说明、归档）
legacy/         # 历史入口归档（不建议新功能继续使用）
```

详细文档见：[docs/README.md](docs/README.md)。

## 发布（GitHub）

项目当前版本：`v2.0.0`。

建议流程：
1. 合并变更到 `main`
2. 打 tag（例如 `v2.0.1`）
3. 推送 `main` 与 tag
4. 在 GitHub Releases 页面基于 tag 发布 release

示例命令：

```bash
git checkout main
git pull --ff-only

git tag -a v2.0.1 -m "Release v2.0.1"
git push origin main
git push origin v2.0.1
```

