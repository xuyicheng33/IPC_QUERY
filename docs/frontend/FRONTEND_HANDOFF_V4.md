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

## 4. 类型合同

核心类型定义位于：`frontend/src/lib/types.ts`

重点关注：

- `SearchState`
- `SearchResponse`
- `PartPayload`
- `PartDetailResponse`
- `DocsTreeResponse`
- `DbRowActionState`

## 5. 开发与构建

```bash
npm --prefix frontend install
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

构建产物输出到 `web/`。

## 6. 回归建议

发布前至少手工走查：

1. 首页输入查询并跳转搜索结果；
2. 搜索页分页与排序切换；
3. 详情页打开 PDF、显示页脚元信息；
4. DB 页执行一组文件操作（改名/移动/删除）并确认 UI 状态反馈；
5. 关键 API 报错场景（404/409）前端可读。
