# 目录结构规范

## 一级目录职责

- `ipc_query/`: 主应用代码（API/服务/数据库/配置）
- `cli/`: 命令行入口定义
- `web/`: 前端静态资源
- `tests/`: 单元和集成测试
- `scripts/`: 辅助脚本实现
- `data/fixtures/`: 受版本管理的样本与固定数据
- `docs/`: 维护与结构文档

## scripts 目录规则

- `scripts/qa/`: QA 样本生成、校验、PDF truth 工具
- `scripts/tools/`: 查询、数据库对比等实用工具
- 根目录同名脚本仅作为兼容薄包装，不放具体实现

## data/fixtures 目录规则

- `data/fixtures/qa/baseline/`: 长期保留的基线样本
- `data/fixtures/qa/archive/`: 自动生成或历史样本归档

## 新文件放置决策表

| 文件类型 | 放置位置 |
|---|---|
| 主服务代码 | `ipc_query/` |
| CLI 参数与命令定义 | `cli/` |
| QA 检查/生成脚本 | `scripts/qa/` |
| 临时分析/比对工具 | `scripts/tools/` |
| 需提交的样本数据 | `data/fixtures/` |
| 运行态临时产物 | `tmp/`（不提交） |
| 维护说明文档 | `docs/` |
