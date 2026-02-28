# IPC_QUERY 前端交接说明（release3 / v3.0.0）

本文档用于支持设计师和前端重构同学快速上手当前实现，明确：

1. 现有页面布局和交互。
2. 前端组件与状态模型关系。
3. 与后端 API 的对应关系。
4. 完全重构时必须保持的兼容合同。

## 1. 快速入口

### 1.1 运行方式

```bash
python3 -m ipc_query serve --db ./data/ipc.sqlite --port 8791
```

访问：

- 首页：`/`
- 搜索页：`/search`
- 详情页：`/part/{id}`
- DB 管理页：`/db`

### 1.2 前端构建

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

构建产物输出到 `web/`，由 Python 服务静态托管。

## 2. 设计基线（release3）

### 2.0 设计范围约束（强约束）

从本次改版开始，前端视觉与交互设计采用 **Desktop-only** 策略：

1. 仅设计和验收全屏桌面端体验，不进行移动端设计。
2. 不再以手机端可用性作为评审标准，不为移动端新增专门布局方案。
3. 新需求评审、UI 走查、视觉对齐、验收截图均以桌面端为准。

桌面验收基线（建议）：

1. `1920 x 1080`（主验收分辨率）
2. `1536 x 864`（兼容验收分辨率）
3. `1366 x 768`（最小验收分辨率）

工程执行约束：

1. 以桌面信息密度和操作效率优先，不为移动端妥协主布局。
2. 后续开发如涉及响应式代码，仅保留不影响桌面方案的最低限度兼容，不作为设计目标。
3. 所有页面优化讨论默认以桌面全屏视觉稿和桌面交互路径为唯一目标。

### 2.1 总体视觉方向

1. Refined Minimal（克制、低噪音、轻层级）。
2. 顶部左侧标题默认隐藏，仅保留右侧胶囊按钮组。
3. 操作按钮统一高度和圆角（胶囊化），跨页面规格一致。

### 2.2 全局导航

入口组件：`frontend/src/components/layout/AppShell.tsx`

关键规则：

1. `hideHeaderTitle` 默认 `true`。
2. 顶部只显示右侧按钮组（例如“返回上一级 / 搜索 / 数据库”）。
3. 回退按钮优先 `history.back()`，无历史时回落 `backHref`。

按钮规格组件：`frontend/src/components/ui/Button.tsx`

1. 统一 `minHeight: 38`、超圆角、字重 600。
2. 语义变体仍保留：`primary / ghost / danger`。

## 3. 页面布局与交互

### 3.1 首页 `/`

文件：`frontend/src/pages/HomePage.tsx`

布局：

1. 页面主区域垂直居中。
2. 仅保留一个搜索输入框和一个“搜索”按钮。
3. 不展示标题文案和提示 chips。

交互：

1. 输入非空后提交，跳转 `/search?q=...&match=pn&page=1`。
2. 与后端仅通过 URL 参数衔接，不直接请求 API。

### 3.2 搜索页 `/search`

文件：`frontend/src/pages/SearchPage.tsx`

当前仍保留：

1. 查询输入、匹配模式、来源目录/文档过滤、分页。
2. 点击结果行跳转详情页，并携带上下文参数。

说明：

1. release3 主要重构首页与 DB 页。
2. 搜索页核心查询逻辑保持兼容。

### 3.3 详情页 `/part/{id}`

文件：`frontend/src/pages/PartDetailPage.tsx`

当前包含：

1. 零件元信息、层级关系、关键词高亮。
2. 跳转原 PDF 与 viewer。
3. 顶部导航规格已对齐全局胶囊按钮体系。

### 3.4 DB 管理页 `/db`

主文件：`frontend/src/pages/DbPage.tsx`

release3 结构：

1. 单栏布局（移除左侧目录树）。
2. 顶部信息区：路径面包屑 + 文件数 + 选中数。
3. 工具栏动作：上传 PDF、创建子目录、删除所选、刷新。
4. 列表区：无表头单列 Finder 风格。
5. 反馈区：顶部轻量状态条 + 右上角短暂 Toast。
6. 任务状态面板不展示（内部仍保持轮询机制）。

列表交互（`frontend/src/pages/db/DbFileTable.tsx`）：

1. 同时渲染目录项与文件项。
2. 目录项：
   - 单击高亮。
   - 双击进入目录。
3. 文件项：
   - 左侧复选框参与批量删除。
   - 右侧 hover 时显示操作胶囊（预览 / 改名 / 移动 / 删除）。

目录约束（release3 决策）：

1. 仅支持根目录及一级子目录导航。
2. 仅支持在根目录创建子目录。

对应实现：

- `frontend/src/pages/db/useDbDirectoryModel.ts`
- `frontend/src/pages/db/useDbOperations.ts`

## 4. 前端模块结构（DB）

### 4.1 目录模型

`useDbDirectoryModel.ts`

职责：

1. 当前目录路径与缓存管理。
2. 目录/文件列表加载。
3. 选择状态维护与路径同步。
4. 根目录一级子目录约束。

### 4.2 任务轮询模型

`useDbJobsPolling.ts`

职责：

1. 导入任务和扫描任务轮询。
2. 轮询完成后触发目录刷新。
3. 任务结果用于内部状态，不要求 UI 面板展示。

### 4.3 动作模型

`useDbOperations.ts`

职责：

1. 上传、批量删除、创建目录、重命名、移动、扫描触发。
2. 统一 action 状态（`idle/pending/success/error`）。
3. 提供全局反馈文案供状态条与 toast 渲染。

## 5. UI 与后端 API 对照

| UI 入口 | Method | API | 说明 |
|---|---|---|---|
| 搜索提交 | GET | `/api/search` | 查询零件列表 |
| 详情加载 | GET | `/api/part/{id}` | 读取零件详情 |
| DB 当前目录加载 | GET | `/api/docs/tree?path={dir}` | 获取目录和文件 |
| DB 上传 PDF | POST | `/api/import` | 创建导入任务 |
| DB 上传任务轮询（内部） | GET | `/api/import/{job_id}` | 查询导入任务状态 |
| DB 删除所选 | POST | `/api/docs/batch-delete` | 批量删除 |
| DB 单文件改名 | POST | `/api/docs/rename` | 改名并更新索引 |
| DB 单文件移动 | POST | `/api/docs/move` | 移动并更新索引 |
| DB 创建子目录 | POST | `/api/folders` | 创建目录 |
| DB 扫描触发（API保留） | POST | `/api/scan` | release3 UI 默认不暴露按钮 |
| 健康状态 | GET | `/api/health` | 返回版本与 DB 健康信息 |
| 能力检测 | GET | `/api/capabilities` | 上传/扫描可用性 |

## 6. 关键数据契约（前端）

类型文件：`frontend/src/lib/types.ts`

重点：

1. `SearchResponse` / `PartDetailResponse`：搜索与详情合同。
2. `DocsTreeResponse`：目录树接口返回合同。
3. `DbListItem`：release3 列表统一渲染项（目录+文件）。
4. `DbRowActionState`：行内改名/移动状态机合同。
5. `PartPayload`（详情页）新增页脚元信息字段：`figure_label`、`date_text`、`page_token`、`rf_text`。
6. 新增字段为向后兼容扩展：无值可为 `null/undefined`，其中 `rf_text` 建议“无值不渲染该项”。

## 7. 完全重构时的必守兼容项

### 7.1 必守路由

1. `/`
2. `/search`
3. `/db`
4. `/part/{id}`
5. `/viewer.html`

### 7.2 必守 URL 参数

1. `q`
2. `match`
3. `page`
4. `include_notes`
5. `source_dir`
6. `source_pdf`

### 7.3 必守 API 语义

1. `/api/search`
2. `/api/part/{id}`
3. `/api/docs*`
4. `/api/import*`
5. `/api/scan*`
6. `/render/*`
7. `/pdf/*`

### 7.4 构建与部署约束

1. 仍使用 Vite 多入口构建。
2. 构建产物仍输出到 `web/`。
3. Python 服务继续静态托管 `web/`。

## 8. 设计师协作建议

1. 先在 Figma 固化三类统一组件：顶栏胶囊按钮、列表行、状态反馈条。
2. 先做信息架构和交互走查，再做高保真视觉细化。
3. 重构期间优先保留页面行为合同，再替换视觉层。
4. 任何涉及路径层级策略变更（例如恢复多级目录）需先同步后端/前端约束。

## 9. release3 回归清单

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
pytest -q
node --test tests/web/*.test.mjs
```

手工验收关键路径：

1. 首页极简搜索可跳转查询。
2. DB 页单栏布局下上传/删除/改名/移动/刷新可用。
3. DB 面包屑与目录双击进入一致。
4. Toast 与状态条在成功/失败场景可见。
5. `/api/health` 返回版本应为 `3.0.0`。
