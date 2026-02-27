# IPC_QUERY DB 模块化验收（M4）

本文档用于验收 `/db` 页在 MD3 收口阶段的模块化深度与行为稳定性。

## 1. 模块边界

### 1.1 目录领域模型

- `frontend/src/pages/db/useDbDirectoryModel.ts`
- 职责：
  - `currentPath/treeCache/directories/files/selectedPaths` 状态管理
  - 目录加载链路：`ensureTreeNode -> preloadPathChain -> loadDirectory`
  - 目录切换与选择逻辑
  - 根目录 + 一级子目录约束

### 1.2 任务轮询模型

- `frontend/src/pages/db/useDbJobsPolling.ts`
- 职责：
  - 导入/重扫任务追踪
  - 轮询拉取任务状态
  - 任务完成后触发目录刷新（可不直接展示任务列表面板）

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
  - 采用单栏 Finder 风格（无左侧目录树、无任务状态卡片）

## 2. 行为验收清单

1. 上传 PDF：可提交、任务可轮询、成功后目录自动刷新。
2. 批量删除：确认弹窗、部分失败可见、成功后选择清空并刷新目录。
3. 重扫目录：API 与内部轮询保留，UI 默认不提供主按钮入口。
4. 创建目录：输入有效名后可创建，成功后刷新并提示。
5. 创建目录限制：仅支持根目录创建一级子目录。
6. 改名/移动：行内状态机完整（pending、error 可见，成功刷新）。
7. 目录交互：面包屑导航与目录双击进入行为稳定。
8. 服务禁用态：导入关闭时，上传/删改/建目录有明确禁用反馈。
9. 反馈：顶部状态条 + Toast 正常显示成功/失败状态。

## 3. 验收命令

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
pytest -q
node --test tests/web/*.test.mjs
```
