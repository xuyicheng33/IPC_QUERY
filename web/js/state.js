/**
 * 状态管理模块
 * 管理应用的全局状态
 */

/**
 * 应用状态类
 */
export class AppState {
  constructor() {
    // 查询状态
    this.query = "";
    this.match = "pn";
    this.currentPage = 1;
    this.totalResults = 0;

    // 选中状态
    this.activeId = null;

    // 结果数据
    this.results = [];
    this.hasSearched = false;

    // 详情数据
    this.currentDetail = null;
    this.currentTermText = "";
    this.currentTermHas = { replace: false, optional: false };

    // 导航历史
    this.navStack = [];

    // 文档缓存
    this.docsCache = null;

    // UI状态
    this.loading = false;
    this.error = null;
    this.isRestoring = false;

    // 监听器
    this._listeners = [];
  }

  /**
   * 订阅状态变化
   */
  subscribe(listener) {
    this._listeners.push(listener);
    return () => {
      this._listeners = this._listeners.filter((l) => l !== listener);
    };
  }

  /**
   * 通知状态变化
   */
  notify() {
    for (const listener of this._listeners) {
      listener(this);
    }
  }

  /**
   * 设置查询
   */
  setQuery(query, match = this.match) {
    this.query = query;
    this.match = match;
    this.currentPage = 1;
    this.activeId = null;
    this.notify();
  }

  /**
   * 设置结果
   */
  setResults(results, total, page = 1) {
    this.results = results;
    this.totalResults = total;
    this.currentPage = page;
    this.hasSearched = true;
    this.loading = false;
    this.notify();
  }

  /**
   * 设置选中ID
   */
  setActiveId(id) {
    this.activeId = id;
    this.notify();
  }

  /**
   * 设置详情
   */
  setDetail(detail) {
    this.currentDetail = detail;
    this.notify();
  }

  /**
   * 设置加载状态
   */
  setLoading(loading) {
    this.loading = loading;
    if (loading) {
      this.error = null;
    }
    this.notify();
  }

  /**
   * 设置错误
   */
  setError(error) {
    this.error = error;
    this.loading = false;
    this.notify();
  }

  /**
   * 设置页面
   */
  setPage(page) {
    this.currentPage = page;
    this.notify();
  }

  /**
   * 推入导航栈
   */
  pushNav(item) {
    this.navStack.push(item);
  }

  /**
   * 弹出导航栈
   */
  popNav() {
    return this.navStack.pop();
  }

  /**
   * 清空导航栈
   */
  clearNav() {
    this.navStack = [];
  }
}

/**
 * URL状态管理
 */
export function readUrlState() {
  const params = new URLSearchParams(window.location.search || "");
  const q = (params.get("q") || "").toString();
  const idRaw = (params.get("id") || "").toString();
  const id = /^\d+$/.test(idRaw) ? Number(idRaw) : null;
  const pageRaw = (params.get("p") || "").toString();
  const page = /^\d+$/.test(pageRaw) ? Math.max(1, Number(pageRaw)) : 1;
  const matchRaw = (params.get("m") || "pn").toString();
  const match = ["all", "pn", "term"].includes(matchRaw) ? matchRaw : "pn";
  return { q, id, page, match };
}

export function writeUrlState(next, opts = {}) {
  const replace = Boolean(opts.replace);
  const q = (next?.q || "").toString().trim();
  const id = typeof next?.id === "number" && Number.isFinite(next.id) ? next.id : null;
  const page = typeof next?.page === "number" && Number.isFinite(next.page) ? Math.max(1, Math.floor(next.page)) : 1;
  const match = (next?.match || "all").toString();

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (id) params.set("id", String(id));
  if (q && page > 1) params.set("p", String(page));
  if (q && match && match !== "pn") params.set("m", match);
  const qs = params.toString();
  const url = `${window.location.pathname}${qs ? `?${qs}` : ""}`;

  const state = { q, id, page, match };
  if (replace) history.replaceState(state, "", url);
  else history.pushState(state, "", url);
}

// 全局状态实例
export const appState = new AppState();
