# IPC_QUERY DB 模块化验收（M4）

本文档用于验收 `/db` 页在 MD3 收口阶段的模块化深度与行为稳定性。

## 1. 模块边界

### 1.1 目录领域模型

- `frontend/src/pages/db/useDbDirectoryModel.ts`
- 职责：
  - `currentPath/treeCache/expandedDirs/files/selectedPaths` 状态管理
  - 目录加载链路：`ensureTreeNode -> preloadPathChain -> loadDirectory`
  - 目录切换、展开、选择逻辑

### 1.2 任务轮询模型

- `frontend/src/pages/db/useDbJobsPolling.ts`
- 职责：
  - 导入/重扫任务追踪
  - 轮询拉取任务状态
  - 任务状态聚合（jobs + file job status map）

### 1.3 动作模型

- `frontend/src/pages/db/useDbOperations.ts`
- 职责：
  - 全局动作：`upload/batchDelete/rescan/createFolder`
  - 行内动作：`rename/move`
  - 状态机统一：`idle -> pending -> success/error`

### 1.4 页面编排壳

- `frontend/src/pages/DbPage.tsx`
- 要求：
  - 只负责组合 hook 输出和 UI 组件 props
  - 不直接承载轮询循环与具体动作实现细节

## 2. 行为验收清单

1. 上传 PDF：可提交、任务可轮询、成功后目录自动刷新。
2. 批量删除：确认弹窗、部分失败可见、成功后选择清空并刷新目录。
3. 重扫目录：任务提交成功、轮询状态可见、任务完成后刷新目录。
4. 创建目录：输入有效名后可创建，成功后刷新并提示。
5. 改名/移动：行内状态机完整（pending、error 可见，成功刷新）。
6. 目录树：展开/收起、切换目录、刷新树稳定。
7. 服务禁用态：导入或重扫关闭时，操作有明确禁用反馈。

## 3. 验收命令

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
pytest -q
node --test tests/web/*.test.mjs
```
