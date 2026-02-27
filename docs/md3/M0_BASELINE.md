# IPC_QUERY MD3 基线（M0）

本文档是当前 MD3 改造口径下的基线定义，作为后续回归与发布验收依据。

## 1. 目标与范围

1. 前端技术栈：React + Vite + MUI v7 + Material Symbols（Rounded）。
2. 主题范围：首期仅浅色主题。
3. 兼容边界：路由、URL 参数、API 语义、localStorage 键名全部保持兼容。

## 2. 公共兼容合同（冻结）

### 2.1 路由兼容

| Public URL | Static Output |
|---|---|
| `/` | `web/index.html` |
| `/search` | `web/search.html` |
| `/db` | `web/db.html` |
| `/part/{id}` | `web/part.html` |
| `/viewer.html` | `web/viewer.html` |

### 2.2 URL 参数兼容

- `q`
- `match`
- `page`
- `include_notes`
- `source_dir`
- `source_pdf`

### 2.3 API 语义兼容

保持现有接口语义不变：

- `/api/search`
- `/api/part/{id}`
- `/api/docs*`
- `/api/import*`
- `/api/scan*`
- `/render/*`
- `/pdf/*`

### 2.4 localStorage 键兼容

- `ipc_search_history`
- `ipc_favorites`

## 3. 依赖与策略决策

1. 使用 MUI 组件体系，不再扩展自研视觉原子组件。
2. 图标体系固定为 Material Symbols Rounded。
3. `@mui/x-tree-view` 当前**不安装、也不使用**（保留后续按需引入可能）。

## 4. 质量门禁

以下命令作为基线回归命令：

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
pytest -q
node --test tests/web/*.test.mjs
```
