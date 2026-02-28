# IPC_QUERY 发布清单（v4.0 起）

## 1. 版本信息

- Python 包版本：`4.0.0`
- Git 标签建议：`v4.0.0`
- GitHub Release 标题建议：`v4.0`

## 2. 发布前质量门禁

```bash
git checkout main
git pull --ff-only

pytest
node --test tests/web/*.test.mjs
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

## 3. 变更确认

- `README.md` 与 `docs/` 文档已同步到当前行为。
- `web/` 已由最新 `frontend/` 源码重新构建。
- `git status` 无意外临时文件。

## 4. 打标签与推送

```bash
git tag -a v4.0.0 -m "Release v4.0.0"
git push origin main
git push origin v4.0.0
```

## 5. 创建 GitHub Release

两种方式任选一种：

### 方式 A：网页

1. 进入仓库 Releases 页面。
2. 点击 “Draft a new release”。
3. 选择 tag：`v4.0.0`。
4. 标题填写：`v4.0`。
5. 说明里至少包含：
   - 主要功能变化
   - 向后兼容注意事项
   - 运行方式（README 链接）

### 方式 B：GitHub CLI

```bash
gh release create v4.0.0 \
  --title "v4.0" \
  --notes "See README.md and docs/GETTING_STARTED.md for full setup steps."
```

## 6. 发布后回归

- `/api/health` 返回 `version=4.0.0`。
- 首页、搜索页、详情页、DB 页可访问。
- 详情页 `/part/{id}` 可打开 PDF 与渲染预览。
