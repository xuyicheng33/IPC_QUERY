# IPC_QUERY

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**IPC_QUERY** 是一个从 IPC (Illustrated Parts Catalog) PDF 文档中提取零件信息并提供查询服务的生产级系统。

## 特性

- 🚀 **高性能搜索** - 支持件号精确匹配和术语模糊搜索
- 📦 **智能数据提取** - 基于坐标的PDF表格提取，避免OCR错列问题
- 💾 **缓存优化** - LRU缓存 + TTL过期，显著提升查询性能
- 🐳 **容器化部署** - Docker支持，一键部署
- 📊 **生产就绪** - 结构化日志、健康检查、监控指标

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/your-org/ipc_query.git
cd ipc_query

# 安装依赖
pip install -e .

# 或仅安装核心依赖
pip install PyMuPDF
```

### 构建数据库

```bash
# 从PDF文件构建数据库
python -m ipc_query build --pdf-dir ./pdfs --output ./data/ipc.sqlite

# 或指定具体PDF文件
python -m ipc_query build --pdf ./doc1.pdf --pdf ./doc2.pdf --output ./data/ipc.sqlite

# 使用原有脚本（兼容）
python build_db.py
```

### 启动服务

```bash
# 使用新架构启动
python -m ipc_query serve --db ./data/ipc.sqlite --port 8791

# 使用原有脚本启动（兼容）
python web_server.py --db ./data/ipc.sqlite --port 8791 --static-dir web

# 访问 http://127.0.0.1:8791
```

### Docker部署

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 使用说明

### 命令行接口

```bash
# 查看帮助
python -m ipc_query --help

# 启动服务
python -m ipc_query serve --db ./data/ipc.sqlite --host 0.0.0.0 --port 8791

# 构建数据库
python -m ipc_query build --output ./data/ipc.sqlite --limit 20

# 命令行查询
python -m ipc_query query "113A4200-2" --db ./data/ipc.sqlite
```

### API接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/search` | GET | 搜索零件 |
| `/api/part/{id}` | GET | 获取零件详情 |
| `/api/docs` | GET | 获取文档列表 |
| `/api/health` | GET | 健康检查 |
| `/api/metrics` | GET | 性能指标 |
| `/api/import` | POST | 上传单个 PDF 并创建导入任务 |
| `/api/import/jobs` | GET | 查询最近导入任务 |
| `/api/import/{job_id}` | GET | 查询指定导入任务状态 |
| `/render/{pdf}/{page}.png` | GET | 渲染PDF页面 |
| `/pdf/{name}` | GET | 下载PDF文件 |

### 搜索示例

```bash
# 件号搜索
curl "http://localhost:8791/api/search?q=113A4200-2&match=pn"

# 术语搜索
curl "http://localhost:8791/api/search?q=replace&match=term"

# 综合搜索
curl "http://localhost:8791/api/search?q=113A4200&match=all&page=1&page_size=20"
```

## 项目结构

```
ipc_query/
├── config.py           # 配置管理
├── constants.py        # 常量定义
├── exceptions.py       # 异常体系
├── db/                 # 数据层
│   ├── connection.py   # 数据库连接
│   ├── models.py       # 数据模型
│   └── repository.py   # 数据访问
├── services/           # 业务逻辑层
│   ├── cache.py        # 缓存服务
│   ├── search.py       # 搜索服务
│   └── render.py       # 渲染服务
├── api/                # 接口层
│   ├── server.py       # HTTP服务器
│   ├── handlers.py     # 请求处理
│   └── middleware.py   # 中间件
└── utils/              # 工具模块
    ├── logger.py       # 日志系统
    └── metrics.py      # 性能指标

web/                    # 前端
├── index.html
├── js/
│   ├── main.js         # 入口
│   ├── api.js          # API调用
│   ├── state.js        # 状态管理
│   ├── components.js   # UI组件
│   └── utils.js        # 工具函数
└── css/
    ├── variables.css   # CSS变量
    ├── base.css        # 基础样式
    ├── components.css  # 组件样式
    └── layout.css      # 布局样式
```

## 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_PATH` | 数据库文件路径（优先） | `data/ipc.sqlite` |
| `DATABASE_URL` | 数据库URL（仅 `sqlite://`，在未设置 `DATABASE_PATH` 时生效） | - |
| `HOST` | 监听地址 | `127.0.0.1` |
| `PORT` | 监听端口 | `8791` |
| `PDF_DIR` | PDF文件目录（用于 `/pdf`/`/render`） | `data/pdfs` |
| `UPLOAD_DIR` | 上传文件保存目录 | `data/pdfs` |
| `IMPORT_MAX_FILE_SIZE_MB` | 上传文件大小上限(MB) | `100` |
| `IMPORT_QUEUE_SIZE` | 导入任务队列长度 | `8` |
| `IMPORT_JOB_TIMEOUT_S` | 导入任务超时预算（秒） | `600` |
| `CACHE_SIZE` | 缓存大小 | `1000` |
| `CACHE_TTL` | 缓存过期时间(秒) | `300` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `LOG_FORMAT` | 日志格式(json/text) | `json` |

### 空库启动与上传入库

```bash
# 不预先构建DB也可启动（会自动初始化空库）
python -m ipc_query serve --db ./data/ipc.sqlite --port 8791

# 上传入库（示例）
curl -X POST "http://127.0.0.1:8791/api/import?filename=sample.pdf" \
  -H "Content-Type: application/pdf" \
  --data-binary "@./sample.pdf"

# 查询任务状态
curl "http://127.0.0.1:8791/api/import/jobs"
```

---

## 原有说明（坐标提取法）

这个目录是一个**独立的新 demo**：用"PDF 文本层 + 固定坐标切列/按 PART NUMBER 的 y 坐标分段"的方法抽取表格，并建 SQLite 供网页查询。

- 运行环境：Python 3.10+
- 依赖安装：`pip install PyMuPDF`
- 默认新库：`tmp/ipc_coords_demo.sqlite`
- 默认端口：`8791`

### 生成新数据库（默认跑 20 份 PDF）

```powershell
$env:PYTHONIOENCODING='utf-8'
python build_db.py
```

默认会从 `IPC/7NG/*___083.pdf`（排除 `*-fm___083.pdf`）里按文件名排序取前 20 个。

你也可以自选 PDF：

```powershell
python build_db.py --pdf IPC/7NG/24-21___083.pdf --pdf IPC/7NG/24-22___083.pdf
python build_db.py --pdf-glob "IPC/7NG/24-*.pdf" --limit 20
python build_db.py --output tmp/ipc_coords_20.sqlite
```

### 命令行查询

```powershell
$env:PYTHONIOENCODING='utf-8'
python query_db.py 113A4200-2 --db tmp/ipc_coords_demo.sqlite
```

### 启动网页（整页预览）

```powershell
$env:PYTHONIOENCODING='utf-8'
python web_server.py --db tmp/ipc_coords_demo.sqlite --port 8791 --static-dir web
```

浏览器打开：`http://127.0.0.1:8791`

PDF 相关：
- `--pdf-dir`：PDF 根目录（用于 `/pdf`/`/render` 定位 PDF；可与 DB 的 `pdf_path` 解耦，方便 Windows 建库后部署到 Linux）

也可以用点号测试层级（`NOMENCLATURE` 前导 `.` / `..`）：直接搜索框输入 `.` 或 `..`。

### 技术说明

- 坐标法优点：对"可复制文本"的 PDF，**件号/列对齐更稳**（不会有 OCR/表格错列的噪声）
- 使用固定的厘米坐标转换为PDF点坐标，精确定位表格区域

---

## 开发

### 运行测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 测试覆盖率
pytest --cov=ipc_query tests/
```

### 代码检查

```bash
# 类型检查
mypy ipc_query
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
