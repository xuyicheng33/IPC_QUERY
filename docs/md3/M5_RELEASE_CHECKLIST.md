# IPC_QUERY MD3 发布收口清单（M5）

## 1. 代码一致性

1. DB 模块边界符合 M4 文档定义。
2. `DbPage.tsx` 仅做编排，不回流大一统状态。
3. 不引入 `@mui/x-tree-view` 依赖。

## 2. 兼容性检查

1. 路由兼容：
   - `/`
   - `/search`
   - `/db`
   - `/part/{id}`
   - `/viewer.html`
2. URL 参数兼容：`q/match/page/include_notes/source_dir/source_pdf`。
3. API 语义兼容：`/api/search`、`/api/part/{id}`、`/api/docs*`、`/api/import*`、`/api/scan*`、`/render/*`、`/pdf/*`。
4. localStorage 键兼容：`ipc_search_history`、`ipc_favorites`。

## 3. 回归命令（必须全绿）

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
pytest -q
node --test tests/web/*.test.mjs
```

## 4. 手工关键路径

1. Search 闭环：查询、筛选、分页、跳详情、回退恢复。
2. Part/Viewer 闭环：返回链路、`pdf/page/scale` 参数同步、键盘翻页。
3. DB 闭环：上传、批删、改名、移动、目录切换（双击进入 + 面包屑返回）、刷新。
4. DB 反馈：顶部状态条与 Toast 在成功/失败场景可见。
5. 可访问性冒烟：键盘可达、焦点可见、控件可读标签。

## 5. 文档一致性门禁

1. `docs/md3/*` 与代码实现一致。
2. `docs/archive/ui-rebuild/*` 仅作为历史口径，不作为当前发布基线。
