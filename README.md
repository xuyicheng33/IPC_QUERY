# IPC_QUERY

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**IPC_QUERY** 是一个从 IPC (Illustrated Parts Catalog) PDF 文档中提取零件信息并提供查询服务的系统。

## 推荐入口与兼容入口

- 推荐：`python -m ipc_query ...`
- 兼容：根目录历史脚本仍可使用（`build_db.py`、`web_server.py`、`query_db.py`、`qa_check.py`、`qa_generate.py`、`compare_with_ipc_db.py`）
- 兼容脚本已转为薄包装，实际实现位于 `scripts/`

## 快速开始

### 安装

```bash
pip install -e .
```

### 构建数据库

```bash
# 推荐
python -m ipc_query build --pdf-dir ./pdfs --output ./data/ipc.sqlite

# 兼容
python build_db.py --output ./data/ipc.sqlite
```

### 启动服务

```bash
# 推荐
python -m ipc_query serve --db ./data/ipc.sqlite --port 8791

# 兼容
python web_server.py --db ./data/ipc.sqlite --port 8791 --static-dir web
```

访问：`http://127.0.0.1:8791`

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/search` | GET | 搜索零件 |
| `/api/part/{id}` | GET | 获取零件详情 |
| `/api/docs` | GET | 获取文档列表 |
| `/api/docs?name={pdf_name}` | DELETE | 删除指定 PDF 及关联数据 |
| `/api/health` | GET | 健康检查 |
| `/api/metrics` | GET | 性能指标 |
| `/api/import` | POST | 上传 PDF 并创建导入任务 |
| `/api/import/jobs` | GET | 查询最近导入任务 |
| `/api/import/{job_id}` | GET | 查询指定导入任务状态 |
| `/render/{pdf}/{page}.png` | GET | 渲染 PDF 页面 |
| `/pdf/{name}` | GET | 获取 PDF 文件 |

## 项目结构

```text
/Users/xuyicheng/Desktop/Study/IPC_QUERY_BASELINE
├── ipc_query/                  # 主应用代码
├── cli/                        # CLI 入口
├── web/                        # 前端静态资源
├── tests/                      # 测试
├── scripts/
│   ├── qa/                     # QA/比对相关脚本实现
│   └── tools/                  # 其他工具脚本实现
├── data/
│   └── fixtures/
│       └── qa/
│           ├── baseline/       # 基线样本
│           └── archive/        # 自动/历史样本
├── docs/
│   ├── STRUCTURE.md            # 目录结构与职责说明
│   └── MAINTENANCE.md          # 清理规则与维护流程
├── build_db.py                 # 兼容入口（保留）
├── web_server.py               # 兼容入口（保留）
├── query_db.py                 # 兼容入口（薄包装）
└── README.md
```

## QA 与工具脚本

### 推荐路径（实现）

- `python scripts/qa/qa_check.py --db data/ipc.sqlite --samples data/fixtures/qa/baseline/qa_samples.json`
- `python scripts/qa/qa_generate.py --pdf /path/to/sample.pdf`
- `python scripts/tools/query_db.py 113A4200-2 --db data/ipc.sqlite`
- `python scripts/tools/compare_with_ipc_db.py --coords-db data/ipc.sqlite --ipc-db ipc.db`

### 兼容路径（薄包装）

- `python qa_check.py ...`
- `python qa_generate.py ...`
- `python query_db.py ...`
- `python compare_with_ipc_db.py ...`

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
| `CACHE_SIZE` | 缓存大小 | `1000` |
| `CACHE_TTL` | 缓存过期时间(秒) | `300` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `LOG_FORMAT` | 日志格式(json/text) | `json` |

## 开发

### 测试

```bash
pytest
```

### 类型检查

```bash
mypy ipc_query
```

### 维护文档

- 目录规范：`docs/STRUCTURE.md`
- 清理规则：`docs/MAINTENANCE.md`

## 许可证

MIT License
