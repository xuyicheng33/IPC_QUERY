# IPC_QUERY 快速上手（本地）

本指南用于在开发机上完成最小可运行闭环。

如果你是要部署到云服务器，请直接阅读 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 1. 前置要求

- Python 3.10+
- Node.js 18+（推荐 20+）
- npm 9+

## 2. 获取代码

```bash
git clone git@github.com:xuyicheng33/IPC_QUERY.git
cd IPC_QUERY
```

## 3. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
npm --prefix frontend install
```

## 4. 构建前端资源

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

构建产物会输出到 `web/`，由后端服务直接托管。

## 5. 准备数据

### 5.1 准备 PDF

将 IPC PDF 放入 `data/pdfs/`（可自行创建目录）。

### 5.2 首次建库

```bash
python3 -m ipc_query build \
  --pdf-dir ./data/pdfs \
  --output ./data/ipc.sqlite
```

## 6. 启动服务

```bash
python3 -m ipc_query serve \
  --db ./data/ipc.sqlite \
  --host 127.0.0.1 \
  --port 8791 \
  --pdf-dir ./data/pdfs \
  --upload-dir ./data/pdfs
```

浏览器访问：`http://127.0.0.1:8791`

## 7. 功能走查建议

1. 首页 `/`：输入件号或术语进行搜索。
2. 搜索页 `/search`：验证分页、排序、筛选。
3. 详情页 `/part/{id}`：验证层级关系、预览图、PDF 跳转。
4. 文档页 `/db`：验证目录管理与文档管理能力。

## 8. 常见问题

### 8.1 上传/扫描能力不可用

检查 `GET /api/capabilities`：
- `import_enabled`
- `scan_enabled`
- `import_reason`
- `scan_reason`
- `write_auth_mode` / `write_auth_required`
- `directory_policy`（v4.0 固定为 `single_level`）

### 8.2 详情页 PDF 无法打开

检查：
- 文档对应文件是否真实存在于 `--pdf-dir` 下
- 直接访问 `/pdf/{relative_path}` 是否返回文件

### 8.3 写接口返回 401（UNAUTHORIZED）

检查：
- 是否开启了 `WRITE_API_AUTH_MODE=api_key`
- 请求头是否携带 `X-API-Key: <WRITE_API_KEY>`
- 写接口范围包括导入/删除/改名/移动/建目录/删目录/扫描

### 8.4 目录操作被拒绝（single-level policy）

v4.0 当前仅支持根目录和一级子目录：
- 允许：`""`、`engine`
- 拒绝：`a/b`、`a/b/c`

### 8.3 修改前端后页面不生效

重新执行：

```bash
npm --prefix frontend run build
```

## 9. 提交前最小检查

```bash
pytest
node --test tests/web/*.test.mjs
npm --prefix frontend run typecheck
npm --prefix frontend run build
python3 -m mypy ipc_query cli
```
