# IPC_QUERY

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](https://opensource.org/licenses/MIT)

IPC_QUERY 是一个从 IPC (Illustrated Parts Catalog) PDF 文档中提取零件信息并提供查询服务的系统。

## 推荐入口

- 应用入口：`python3 -m ipc_query ...`
- 脚本入口：`scripts/` 下按类别组织
- 兼容入口：仅保留 `build_db.py`（壳文件，实际实现位于 `ipc_query/build_db.py`）
- 历史入口：已归档到 `legacy/`

## 快速开始

### 安装

```bash
pip install -e .
```

说明：在本项目的示例环境中请优先使用 `python3`（部分系统未提供 `python` 命令别名）。

### 构建数据库

```bash
# 推荐
python3 -m ipc_query build --pdf-dir ./pdfs --output ./data/ipc.sqlite

# 兼容（仅保留）
python3 build_db.py --output ./data/ipc.sqlite
```

### 启动服务

```bash
python3 -m ipc_query serve --db ./data/ipc.sqlite --port 8791
```

访问：`http://127.0.0.1:8791`

## Web 交互

- 首页：`/`（仅标题 + 搜索框 + 搜索按钮）
- 结果页：`/search`（支持来源目录/文档、匹配模式、备注筛选）
- 详情页：`/part/{id}`（保留术语、层级、预览、打开 PDF，包含 optional/replace 卡片与术语高亮）
- 数据库页：`/db`（双栏文件管理器：左侧目录树，右侧文件表；支持多选删除、批量上传、重扫、创建子目录）

服务启动后会自动提交一次 PDF 目录增量扫描任务（新增/变更文件入库）。

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/search` | GET | 搜索零件 |
| `/api/part/{id}` | GET | 获取零件详情 |
| `/api/docs` | GET | 获取文档列表 |
| `/api/docs/tree?path={relative_dir}` | GET | 获取目录树（子目录 + PDF 文件 + 入库状态） |
| `/api/docs?name={pdf_name}` | DELETE | 删除指定 PDF 及关联数据 |
| `/api/docs/batch-delete` | POST | 批量删除 PDF（逐项返回成功/失败） |
| `/api/health` | GET | 健康检查 |
| `/api/metrics` | GET | 性能指标 |
| `/api/import` | POST | 上传 PDF 并创建导入任务（支持 `target_dir`） |
| `/api/import/jobs` | GET | 查询最近导入任务 |
| `/api/import/{job_id}` | GET | 查询指定导入任务状态 |
| `/api/folders` | POST | 创建子目录 |
| `/api/scan` | POST | 触发增量重扫任务 |
| `/api/scan/{job_id}` | GET | 查询重扫任务状态 |
| `/render/{pdf}/{page}.png` | GET | 渲染 PDF 页面 |
| `/pdf/{name}` | GET | 获取 PDF 文件 |

## 目录结构

```text
/Users/xuyicheng/Desktop/Study/IPC_QUERY_BASELINE
├── ipc_query/                  # 主应用代码（含 build_db 实现）
├── cli/                        # CLI 入口
├── web/                        # 前端静态资源
├── tests/                      # 测试
├── scripts/
│   ├── qa/                     # QA/比对相关脚本
│   └── tools/                  # 其他工具脚本
├── data/
│   └── fixtures/
│       └── qa/
│           ├── baseline/       # 基线样本
│           └── archive/        # 自动/历史样本
├── docs/
│   ├── STRUCTURE.md            # 目录结构说明
│   └── MAINTENANCE.md          # 清理与维护流程
├── legacy/                     # 历史入口与历史资料归档
├── build_db.py                 # 兼容壳入口（转发到 ipc_query.build_db）
└── README.md
```

## 脚本说明

### QA 脚本

- `python3 scripts/qa/qa_check.py --db data/ipc.sqlite --samples data/fixtures/qa/baseline/qa_samples.json`
- `python3 scripts/qa/qa_generate.py --pdf /path/to/sample.pdf`

### 工具脚本

- `python3 scripts/tools/query_db.py 113A4200-2 --db data/ipc.sqlite`
- `python3 scripts/tools/compare_with_ipc_db.py --coords-db data/ipc.sqlite --ipc-db ipc.db`

## 配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_PATH` | 数据库文件路径（优先） | `data/ipc.sqlite` |
| `DATABASE_URL` | 数据库 URL（仅 `sqlite:`） | - |
| `HOST` | 监听地址 | `127.0.0.1` |
| `PORT` | 监听端口 | `8791` |
| `PDF_DIR` | PDF 文件目录 | `data/pdfs` |
| `UPLOAD_DIR` | 上传暂存目录 | `data/pdfs` |
| `IMPORT_MAX_FILE_SIZE_MB` | 上传大小上限(MB) | `100` |
| `IMPORT_QUEUE_SIZE` | 导入队列长度 | `8` |
| `IMPORT_JOB_TIMEOUT_S` | 导入超时预算（秒） | `600` |
| `IMPORT_JOBS_RETAINED` | 保留导入任务数 | `1000` |
| `DEFAULT_PAGE_SIZE` | 默认搜索分页大小 | `20` |
| `MAX_PAGE_SIZE` | 最大搜索分页大小 | `100` |
| `CACHE_SIZE` | 缓存大小 | `1000` |
| `CACHE_TTL` | 缓存过期时间(秒) | `300` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `LOG_FORMAT` | 日志格式(json/text) | `json` |

## 开发

```bash
pytest
mypy ipc_query cli
mypy scripts
```

更多维护规范见：

- `docs/STRUCTURE.md`
- `docs/MAINTENANCE.md`
