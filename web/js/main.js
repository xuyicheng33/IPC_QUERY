/**
 * 主入口模块
 * 应用初始化和主逻辑
 */

import { $, escapeHtml, tokenizeQuery, debounce, detectTermKeywords } from "./utils.js";
import { searchParts, getPartDetail, getDocuments } from "./api.js";
import { appState, readUrlState, writeUrlState } from "./state.js";
import {
  createResultCard,
  renderDetailPanel,
  renderPagination,
  showToast,
  showSkeleton,
  showEmptyState,
  showErrorState,
} from "./components.js";

// 配置
const PAGE_SIZE = 80;
const DEBOUNCE_DELAY = 150;

// DOM元素
const elements = {
  searchInput: null,
  searchForm: null,
  filterBtns: null,
  resultsList: null,
  detailPanel: null,
  pager: null,
  meta: null,
};

/**
 * 初始化应用
 */
function init() {
  // 获取DOM元素
  elements.searchInput = $("#searchInput");
  elements.searchForm = $("#searchForm");
  elements.filterBtns = $$(".filterBtn");
  elements.resultsList = $("#resultsList");
  elements.detailPanel = $("#detailPanel");
  elements.pager = $("#pager");
  elements.meta = $("#meta");

  // 绑定事件
  bindEvents();

  // 从URL恢复状态
  restoreFromUrl();

  // 监听浏览器导航
  window.addEventListener("popstate", handlePopState);

  // 订阅状态变化
  appState.subscribe(handleStateChange);
}

/**
 * 绑定事件
 */
function bindEvents() {
  // 搜索表单
  if (elements.searchForm) {
    elements.searchForm.addEventListener("submit", (e) => {
      e.preventDefault();
      handleSearch();
    });
  }

  // 搜索输入
  if (elements.searchInput) {
    elements.searchInput.addEventListener(
      "input",
      debounce(() => {
        if (elements.searchInput.value.trim()) {
          handleSearch();
        }
      }, DEBOUNCE_DELAY)
    );

    // 键盘快捷键
    elements.searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSearch();
      }
    });
  }

  // 筛选按钮
  elements.filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const match = btn.dataset.match;
      appState.setQuery(elements.searchInput?.value || "", match);
      handleSearch();
    });
  });

  // 结果列表点击
  if (elements.resultsList) {
    elements.resultsList.addEventListener("click", (e) => {
      const card = e.target.closest(".card");
      if (card && card.dataset.id) {
        selectPart(Number(card.dataset.id));
      }
    });
  }

  // 详情面板层级导航点击
  if (elements.detailPanel) {
    elements.detailPanel.addEventListener("click", (e) => {
      const btn = e.target.closest(".hierBtn");
      if (btn && btn.dataset.id) {
        selectPart(Number(btn.dataset.id));
      }
    });
  }

  // 分页点击
  if (elements.pager) {
    elements.pager.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-page]");
      if (btn) {
        const page = Number(btn.dataset.page);
        appState.setPage(page);
        handleSearch();
      }
    });
  }

  // 全局键盘快捷键
  document.addEventListener("keydown", (e) => {
    // Ctrl/Cmd + K 聚焦搜索
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      elements.searchInput?.focus();
    }

    // Esc 关闭详情
    if (e.key === "Escape") {
      appState.setActiveId(null);
    }
  });
}

/**
 * 处理搜索
 */
async function handleSearch() {
  const query = elements.searchInput?.value?.trim() || "";
  if (!query) return;

  appState.setLoading(true);

  try {
    const result = await searchParts({
      q: query,
      match: appState.match,
      page: appState.currentPage,
      page_size: PAGE_SIZE,
    });

    appState.setResults(result.results || [], result.total || 0, appState.currentPage);

    // 更新URL
    writeUrlState({
      q: query,
      match: appState.match,
      page: appState.currentPage,
    });
  } catch (error) {
    console.error("Search failed:", error);
    appState.setError(error.message);
    showToast("搜索失败：" + error.message, "error");
  }
}

/**
 * 选择零件
 */
async function selectPart(partId) {
  appState.setActiveId(partId);

  // 更新URL
  writeUrlState({
    q: appState.query,
    match: appState.match,
    page: appState.currentPage,
    id: partId,
  });

  try {
    const detail = await getPartDetail(partId);
    appState.setDetail(detail);

    // 检测关键词
    const termText = detail.part?.nomenclature_full || detail.part?.nomenclature || "";
    appState.currentTermText = termText;
    appState.currentTermHas = detectTermKeywords(termText);
  } catch (error) {
    console.error("Failed to get part detail:", error);
    showToast("获取详情失败", "error");
  }
}

/**
 * 处理状态变化
 */
function handleStateChange(state) {
  // 更新结果列表
  if (state.results !== undefined) {
    renderResults(state.results, state.query);
  }

  // 更新详情面板
  if (state.currentDetail !== undefined) {
    renderDetail(state.currentDetail);
  }

  // 更新分页
  if (state.hasSearched) {
    renderPager();
  }

  // 更新加载状态
  if (state.loading) {
    showSkeleton(elements.resultsList, 10);
  }
}

/**
 * 渲染结果列表
 */
function renderResults(results, query) {
  if (!elements.resultsList) return;

  if (!results || results.length === 0) {
    showEmptyState(elements.resultsList, "未找到匹配结果");
    return;
  }

  const tokens = tokenizeQuery(query);
  let html = "";

  for (const result of results) {
    const isActive = result.id === appState.activeId;
    html += createResultCard(result, tokens, isActive).outerHTML;
  }

  elements.resultsList.innerHTML = html;
}

/**
 * 渲染详情
 */
function renderDetail(detail) {
  if (!elements.detailPanel) return;

  if (!detail) {
    elements.detailPanel.innerHTML = '<div class="emptyState">选择零件查看详情</div>';
    return;
  }

  elements.detailPanel.innerHTML = renderDetailPanel(detail, appState);
}

/**
 * 渲染分页
 */
function renderPager() {
  if (!elements.pager) return;

  elements.pager.innerHTML = renderPagination(
    appState.currentPage,
    appState.totalResults,
    PAGE_SIZE
  );
}

/**
 * 从URL恢复状态
 */
function restoreFromUrl() {
  const urlState = readUrlState();

  // 恢复搜索框
  if (urlState.q && elements.searchInput) {
    elements.searchInput.value = urlState.q;
  }

  // 恢复匹配模式
  appState.match = urlState.match;

  // 恢复页码
  appState.currentPage = urlState.page;

  // 标记正在恢复
  appState.isRestoring = true;

  // 如果有查询，执行搜索
  if (urlState.q) {
    handleSearch().then(() => {
      // 如果有选中的ID，加载详情
      if (urlState.id) {
        selectPart(urlState.id);
      }
    });
  }

  appState.isRestoring = false;
}

/**
 * 处理浏览器导航
 */
function handlePopState(e) {
  if (e.state) {
    appState.isRestoring = true;

    if (e.state.q && elements.searchInput) {
      elements.searchInput.value = e.state.q;
    }

    appState.match = e.state.match || "pn";
    appState.currentPage = e.state.page || 1;

    if (e.state.q) {
      handleSearch().then(() => {
        if (e.state.id) {
          selectPart(e.state.id);
        }
      });
    }

    appState.isRestoring = false;
  }
}

/**
 * 辅助函数：获取所有匹配元素
 */
function $$(sel) {
  return document.querySelectorAll(sel);
}

// 启动应用
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
