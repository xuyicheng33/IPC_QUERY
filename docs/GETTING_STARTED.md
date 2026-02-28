# IPC_QUERY 快速落地指南（从零跑通）

本指南按“明天要演示给老师”的标准编排，跟着做即可完整跑通。

## 1. 前置准备

### 1.1 必备环境

- Python 3.10+
- Node.js 18+（推荐 20+）
- npm 9+
- macOS / Linux / Windows 均可（命令以 macOS/Linux 为例）

### 1.2 拉代码

```bash
git clone git@github.com:xuyicheng33/IPC_QUERY.git
cd IPC_QUERY
```

## 2. 初始化依赖

### 2.1 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

### 2.2 前端依赖

```bash
npm --prefix frontend install
```

## 3. 构建前端

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

完成后会生成/更新 `web/` 目录下静态资源。

## 4. 准备数据与数据库

### 4.1 准备 PDF

将要检索的 IPC PDF 放到 `data/pdfs/`（可自行新建）。

### 4.2 首次建库

```bash
python3 -m ipc_query build --pdf-dir ./data/pdfs --output ./data/ipc.sqlite
```

如果你已经有可用的 `data/ipc.sqlite`，可跳过建库步骤。

## 5. 启动服务

```bash
python3 -m ipc_query serve \
  --db ./data/ipc.sqlite \
  --host 127.0.0.1 \
  --port 8791 \
  --pdf-dir ./data/pdfs \
  --upload-dir ./data/pdfs
```

打开浏览器：`http://127.0.0.1:8791`

## 6. 演示建议路径

按以下顺序最稳：

1. 首页 `/`：输入件号检索。
2. 搜索页 `/search`：展示分页与排序。
3. 详情页 `/part/{id}`：展示层级关系、术语高亮、PDF 跳转。
4. 文档页 `/db`：展示目录与文件管理能力。

## 7. 常见问题

### 7.1 详情页预览加载失败

- 先确认 `source_relative_path` 对应的 PDF 在 `--pdf-dir` 下存在。
- 直接访问 `/pdf/{relative_path}` 验证文件是否可读。

### 7.2 上传/扫描按钮不可用

- 查看 `/api/capabilities` 返回字段：
  - `import_enabled`
  - `scan_enabled`
  - `import_reason`
  - `scan_reason`
- 常见原因是目录不可写或 `IMPORT_MODE=disabled`。

### 7.3 修改了前端但页面没变化

需要重新执行：

```bash
npm --prefix frontend run build
```

## 8. 提交前最小验证

```bash
pytest
node --test tests/web/*.test.mjs
npm --prefix frontend run typecheck
npm --prefix frontend run build
```
