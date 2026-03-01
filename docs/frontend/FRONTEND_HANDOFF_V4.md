# IPC_QUERY 前端交接说明（v4.0）

## 1. 目标与定位

前端为桌面端查询与运维入口，核心目标：

- 让用户能快速定位 IPC 零件信息；
- 让维护人员在 `/db` 页面完成文件级管理；
- 与后端 API 契约保持稳定、可回归。

## 2. 页面入口

- `/`：首页（搜索起点）
- `/search`：结果列表页
- `/part/{id}`：详情页（层级 + 预览 + PDF）
- `/db`：文档管理页

> 旧版 `/viewer.html` 已下线，不再保留兼容页。

## 3. 关键交互合同

### 3.1 Search 页面

- 支持查询模式：`all` / `pn` / `term`
- 支持排序：`relevance` / `name`
- URL 状态参数可回放：`q/match/sort/page/include_notes/source_dir/source_pdf`
- 点击结果可跳转详情并保留查询上下文。

### 3.2 Part 详情页面

- 顶部显示核心字段：来源、页码、图号、项号、数量、适用号段。
- 页脚元数据显示字段：
  - `figure_label`
  - `date_text`
  - `page_token`
  - `rf_text`（可空）
- “打开 PDF” 按钮跳转至 `/pdf/{relative_path}#page={n}`。
- 预览图来自 `/render/{pdf}/{page}.png`。

### 3.3 DB 页面

- 支持目录进入、改名、删除；
- 支持文件改名、移动、删除；
- 支持双击文件直接预览 PDF；
- 状态反馈统一采用顶部/行内提示。
- 当前目录策略固定为 `single_level`（仅根目录 + 一级子目录）。
- 当 `write_auth_required=true` 时，前端会先检查“会话 API Key”是否已设置，未设置则阻断写操作并提示。
- 会话 API Key 仅保存在页面内存态，刷新后失效（不写入 localStorage/sessionStorage）。
- 批量上传遇到队列满（`429` 或 message 含 `queue is full`）会自动退避重试，并在队列高水位时主动降速提交。
- 当前策略为“持续重试 + 单文件最长等待窗口”，默认单文件最长等待 `60` 分钟后才判定失败。

### 3.4 目录接口路由策略（兼容期）

- Canonical：
  - `POST /api/folders`
  - `POST /api/folders/rename`
  - `POST /api/folders/delete`
- Legacy alias（兼容一个版本周期）：
  - `POST /api/docs/folder/create`
  - `POST /api/docs/folder/rename`
  - `POST /api/docs/folder/delete`
- legacy 路由响应头：
  - `Deprecation: true`
  - `Sunset: 2026-06-30`

## 4. 类型合同

核心类型定义位于：`frontend/src/lib/types.ts`

重点关注：

- `SearchState`
- `SearchResponse`
- `PartPayload`
- `PartDetailResponse`
- `DocsTreeResponse`
- `DbRowActionState`
- `CapabilitiesResponse`（新增 `write_auth_mode` / `write_auth_required` / `directory_policy` 等字段）

## 5. 鉴权与错误语义

- 当后端启用 `WRITE_API_AUTH_MODE=api_key` 时，写接口必须携带 `X-API-Key`。
- 缺失或错误 key 返回 `401` + `UNAUTHORIZED`。
- 导入/扫描队列满返回 `429` + `RATE_LIMITED`，并附带 `Retry-After: 3`。
- 兼容迁移：旧版本队列满语义为 `400 (VALIDATION_ERROR)`，当前版本改为 `429 (RATE_LIMITED)`。
- 服务端异常类（`DatabaseError`/`SearchError`/`RenderError`）统一返回 `500`，不再伪装 `400`。

## 6. 开发与构建

```bash
npm --prefix frontend install
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

构建产物输出到 `web/`。

## 7. 回归建议

发布前至少手工走查：

1. 首页输入查询并跳转搜索结果；
2. 搜索页分页与排序切换；
3. 详情页打开 PDF、显示页脚元信息；
4. DB 页执行一组文件操作（改名/移动/删除）并确认 UI 状态反馈；
5. 关键 API 报错场景（404/409）前端可读。
