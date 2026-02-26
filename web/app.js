/**
 * Application Entry (Legacy)
 *
 * NOTE: This file is the legacy single-file version of the frontend code.
 * A modular version is available in web/js/ which provides better maintainability.
 *
 * This file is kept for reference and will be removed once the modular version
 * is verified to have feature parity.
 *
 * Migration path:
 * - web/js/main.js -> Main entry (ES6 modules)
 * - web/js/api.js -> API calls
 * - web/js/state.js -> State management
 * - web/js/components.js -> UI components
 * - web/js/utils.js -> Utility functions
 */

const $ = (sel) => document.querySelector(sel);

const PAGE_SIZE = 80;
const SHOW_BADGES = false;

function escapeHtml(s) {
  return (s ?? "")
    .toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeRegExp(s) {
  return (s ?? "").toString().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function tokenizeQuery(q) {
  return (q ?? "")
    .toString()
    .trim()
    .split(/\s+/)
    .map((t) => t.trim())
    .filter(Boolean);
}

function highlightHtml(text, tokens) {
  const s = (text ?? "").toString();
  if (!s) return "";
  if (!tokens?.length) return escapeHtml(s);

  const pattern = tokens
    .map((t) => t.trim())
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .map(escapeRegExp)
    .join("|");
  if (!pattern) return escapeHtml(s);

  const re = new RegExp(pattern, "ig");
  let out = "";
  let lastIndex = 0;
  for (const m of s.matchAll(re)) {
    const idx = m.index ?? 0;
    out += escapeHtml(s.slice(lastIndex, idx));
    out += `<span class="hl">${escapeHtml(m[0])}</span>`;
    lastIndex = idx + m[0].length;
  }
  out += escapeHtml(s.slice(lastIndex));
  return out;
}

function detectTermKeywords(text) {
  const s = (text ?? "").toString();
  if (!s.trim()) return { replace: false, optional: false };
  const lower = s.toLowerCase();
  return {
    replace: lower.includes("replace"),
    optional: lower.includes("optional"),
  };
}

function highlightTermKeywordsHtml(text, keywords, focusKeyword) {
  const s = (text ?? "").toString();
  if (!s) return "";
  const kws = (keywords ?? []).map((k) => (k ?? "").toString().trim().toLowerCase()).filter(Boolean);
  if (!kws.length) return escapeHtml(s);

  const pattern = kws.sort((a, b) => b.length - a.length).map(escapeRegExp).join("|");
  if (!pattern) return escapeHtml(s);

  const re = new RegExp(pattern, "ig");
  let out = "";
  let lastIndex = 0;
  for (const m of s.matchAll(re)) {
    const idx = m.index ?? 0;
    const raw = (m[0] ?? "").toString();
    const kw = raw.toLowerCase();
    const focus = focusKeyword && kw === focusKeyword;
    out += escapeHtml(s.slice(lastIndex, idx));
    out += `<span class="hl${focus ? " hlFocus hlPulse" : ""}" data-kw="${escapeHtml(kw)}">${escapeHtml(
      raw
    )}</span>`;
    lastIndex = idx + raw.length;
  }
  out += escapeHtml(s.slice(lastIndex));
  return out;
}

function badge(text, cls = "") {
  const el = document.createElement("span");
  el.className = `badge ${cls}`.trim();
  el.textContent = text;
  return el;
}

function labelRowKind(kind) {
  const k = (kind || "").toString();
  if (!k) return "";
  if (k === "part") return "件";
  if (k === "figure_header") return "图头";
  if (k === "note") return "备注";
  if (k === "boilerplate") return "声明";
  return k;
}

function labelPnMethod(method) {
  const m = (method || "").toString();
  if (!m) return "";
  if (m === "exact") return "精确";
  if (m === "loose") return "近似";
  if (m === "fuzzy") return "模糊";
  if (m === "fuzzy_low") return "模糊(低置信)";
  if (m === "unverified") return "未验证";
  return m;
}

function fmtFig(r) {
  if (!r) return "";
  if (r.fig_item) return r.fig_item;
  return "";
}

function fmtPn(r) {
  return (r.part_number_canonical || r.part_number_extracted || r.part_number_cell || "").toString();
}

function fmtSrc(r) {
  const fig = r.figure_code ? ` ${r.figure_code}` : "";
  const p1 = Number(r.page_num);
  const p2 = Number(r.page_end ?? r.page_num);
  const pr = p2 && p2 !== p1 ? `~${p2}` : "";
  return `${r.source_pdf} · 页${p1}${pr}${fig}`;
}

function fmtUnits(units) {
  const s = (units ?? "").toString().replace(/\s+/g, " ").trim();
  if (!s) return "";
  const m = s.match(/^(RF|AR)\s+(\d+(?:\.\d+)?)$/i);
  if (m) return m[1].toUpperCase();
  return s;
}

async function fetchJson(url) {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return await res.json();
}

function readUrlState() {
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

function writeUrlState(next, opts = {}) {
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

let activeId = null;
let lastQuery = "";
let debounceTimer = null;
let navStack = [];
let docsCache = null;
let isRestoring = false;
let hasSearched = false;
let currentPage = 1;
let currentMatch = "pn";
let totalResults = 0;
let currentTermText = "";
let currentTermHas = { replace: false, optional: false };
let importPollTimer = null;
let latestImportJobId = null;

function updateKeywordCards(has) {
  const applyOne = (kw, cardId, valId, present) => {
    const card = document.getElementById(cardId);
    const val = document.getElementById(valId);
    if (val) val.textContent = present === null ? "—" : present ? "是" : "否";
    if (!card) return;
    const p = present === null ? null : Boolean(present);
    card.title = p === null ? "" : p ? `包含：${kw}` : `不包含：${kw}`;
  };

  applyOne("replace", "kwReplaceCard", "kwReplaceVal", has?.replace ?? null);
  applyOne("optional", "kwOptionalCard", "kwOptionalVal", has?.optional ?? null);
}

function renderTermDesc(opts = {}) {
  const el = $("#desc");
  if (!el) return;

  const text = (currentTermText ?? "").toString();
  if (!text.trim()) {
    el.textContent = "—";
    updateKeywordCards({ replace: false, optional: false });
    return;
  }

  const kws = [];
  if (currentTermHas.replace) kws.push("replace");
  if (currentTermHas.optional) kws.push("optional");

  el.innerHTML = highlightTermKeywordsHtml(text, kws, null);
  updateKeywordCards(currentTermHas);
}

function setResultsWrapVisible(on) {
  const el = $("#resultsWrap");
  if (!el) return;
  el.hidden = !on;
}

function setPagerVisible(on) {
  const el = $("#pager");
  if (!el) return;
  el.hidden = !on;
}

function setSearching(on) {
  const btn = $("#btnSearch");
  if (!btn) return;
  btn.disabled = Boolean(on);
  btn.textContent = on ? "查询中…" : "查询";
}

function syncBodyModalOpen() {
  const anyOpen = Array.from(document.querySelectorAll(".modal")).some((m) => !m.hidden);
  document.body.classList.toggle("modalOpen", anyOpen);
}

function openModal(sel) {
  const modal = $(sel);
  if (!modal) return;
  modal.hidden = false;
  syncBodyModalOpen();
}

function closeModal(sel) {
  const modal = $(sel);
  if (!modal) return;
  modal.hidden = true;
  syncBodyModalOpen();
}

function openDocs() {
  openModal("#docsModal");
}

function closeDocs() {
  closeModal("#docsModal");
}

function setDbChip(ok, text) {
  const chip = $("#dbChip");
  chip.classList.remove("ok", "bad");
  chip.classList.add(ok ? "ok" : "bad");
  $("#dbChip .chipText").textContent = text;
}

function setDocsCount(n) {
  const el = $("#docsCount");
  if (!el) return;
  el.textContent = typeof n === "number" ? `共 ${n} 个 PDF` : "—";
}

function normalizeDocsPayload(docs) {
  if (Array.isArray(docs)) {
    return { documents: docs };
  }
  if (docs && Array.isArray(docs.documents)) {
    return docs;
  }
  return { documents: [] };
}

function renderDocsList(docs) {
  const list = $("#docsList");
  if (!list) return;
  const normalized = normalizeDocsPayload(docs);
  const items = normalized.documents;
  list.innerHTML = "";
  for (const d of items) {
    const name = (d?.pdf_name || "").toString();
    if (!name) continue;
    const row = document.createElement("div");
    row.className = "docRow";

    const a = document.createElement("a");
    a.className = "docItem";
    a.href = `/pdf/${encodeURIComponent(name)}`;
    a.target = "_blank";
    a.rel = "noreferrer";
    a.innerHTML = `<span class="name">${escapeHtml(name)}</span><span class="meta">打开</span>`;

    const btnDelete = document.createElement("button");
    btnDelete.type = "button";
    btnDelete.className = "docDelete";
    btnDelete.textContent = "删除";
    btnDelete.addEventListener("click", async () => {
      await deleteDocByName(name, btnDelete);
    });

    row.appendChild(a);
    row.appendChild(btnDelete);
    list.appendChild(row);
  }
  if (!list.childElementCount) {
    list.innerHTML = `<div class="hint">没有可用的 PDF</div>`;
  }
}

function setImportStatus(text, kind = "neutral") {
  const el = $("#importStatus");
  if (!el) return;
  el.textContent = text || "";
  el.classList.remove("ok", "bad", "running");
  if (kind === "ok") el.classList.add("ok");
  if (kind === "bad") el.classList.add("bad");
  if (kind === "running") el.classList.add("running");
}

async function refreshDocsCache() {
  const docs = await fetchJson("/api/docs");
  docsCache = normalizeDocsPayload(docs);
  const n = docsCache.documents.length;
  setDbChip(true, `DB:${n}`);
  setDocsCount(n);
  renderDocsList(docsCache);
}

function stopImportPolling() {
  if (importPollTimer) {
    clearInterval(importPollTimer);
    importPollTimer = null;
  }
}

function startImportPolling(jobId) {
  stopImportPolling();
  latestImportJobId = jobId;

  let inFlight = false;
  const tick = async () => {
    if (inFlight) return;
    inFlight = true;
    try {
      const job = await fetchJson(`/api/import/${encodeURIComponent(jobId)}`);
      const status = (job?.status || "").toString();
      if (status === "queued") {
        setImportStatus(`任务 ${jobId.slice(0, 8)} 已排队`, "running");
      } else if (status === "running") {
        setImportStatus(`任务 ${jobId.slice(0, 8)} 正在解析…`, "running");
      } else if (status === "success") {
        stopImportPolling();
        const docsIngested = Number(job?.summary?.docs_ingested || 0);
        const partsIngested = Number(job?.summary?.parts_ingested || 0);
        setImportStatus(`导入完成：文档 ${docsIngested}，零件 ${partsIngested}`, "ok");
        await refreshDocsCache();
      } else if (status === "failed") {
        stopImportPolling();
        setImportStatus(`导入失败：${job?.error || "unknown error"}`, "bad");
      }
    } catch (e) {
      stopImportPolling();
      setImportStatus(`任务查询失败：${e?.message || e}`, "bad");
    } finally {
      inFlight = false;
    }
  };

  tick();
  importPollTimer = setInterval(tick, 1500);
}

async function submitImportFile(file) {
  if (!file) {
    setImportStatus("请选择一个 PDF 文件", "bad");
    return;
  }

  setImportStatus(`正在上传：${file.name}`, "running");
  const res = await fetch(`/api/import?filename=${encodeURIComponent(file.name)}`, {
    method: "POST",
    headers: {
      "Content-Type": file.type || "application/pdf",
      "X-File-Name": file.name,
    },
    body: file,
  });

  let data = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }
  if (!res.ok) {
    throw new Error(data?.message || `${res.status} ${res.statusText}`);
  }

  const jobId = (data?.job_id || "").toString();
  if (!jobId) {
    throw new Error("导入任务创建失败");
  }
  setImportStatus(`任务 ${jobId.slice(0, 8)} 已提交`, "running");
  startImportPolling(jobId);
}

async function deleteDocByName(pdfName, triggerBtn = null) {
  const name = (pdfName || "").toString().trim();
  if (!name) {
    setImportStatus("缺少要删除的 PDF 名称", "bad");
    return;
  }

  const confirmed = window.confirm(`确认删除 ${name} 吗？\n将同时删除数据库中的关联记录。`);
  if (!confirmed) return;

  try {
    if (triggerBtn) triggerBtn.disabled = true;
    setImportStatus(`正在删除：${name}`, "running");

    const res = await fetch(`/api/docs?name=${encodeURIComponent(name)}`, {
      method: "DELETE",
      headers: { Accept: "application/json" },
    });
    let data = {};
    try {
      data = await res.json();
    } catch {
      data = {};
    }
    if (!res.ok) {
      throw new Error(data?.message || `${res.status} ${res.statusText}`);
    }

    const parts = Number(data?.deleted_counts?.parts || 0);
    setImportStatus(`删除完成：${name}（零件 ${parts}）`, "ok");
    await refreshDocsCache();

    const currentPdf = ($("#srcPdf")?.textContent || "").toString().trim();
    if (currentPdf && currentPdf === name) {
      closeDetail({ updateUrl: true });
    }

    if (hasSearched && lastQuery) {
      await doSearch(lastQuery, { page: currentPage, match: currentMatch });
    }
  } catch (e) {
    setImportStatus(`删除失败：${e?.message || e}`, "bad");
  } finally {
    if (triggerBtn) triggerBtn.disabled = false;
  }
}

async function init() {
  try {
    await refreshDocsCache();
  } catch {
    setDbChip(false, "DB:ERR");
    setDocsCount(null);
  }
}

function clearActive() {
  closeDetail({ updateUrl: false });
}

function closeDetail(opts = {}) {
  const updateUrl = opts.updateUrl !== false;
  const replaceHistory = Boolean(opts.replaceHistory);

  activeId = null;
  navStack = [];
  document.body.classList.remove("detailOpen");
  $("#detail").hidden = true;
  $("#emptyState").hidden = false;
  $("#results")
    .querySelectorAll(".card.active")
    .forEach((el) => el.classList.remove("active"));
  updateBackButton();

  if (updateUrl && !isRestoring) {
    writeUrlState({ q: lastQuery, id: null, page: currentPage, match: currentMatch }, { replace: replaceHistory });
  }
}

function setStatus(text) {
  $("#statusText").textContent = text;
}

function setCount(shown, total = null) {
  const el = $("#resultsCount");
  if (!el) return;
  if (typeof total === "number" && total > 0) el.textContent = `${shown} / ${total}`;
  else el.textContent = `${shown}`;
}

function updateBackButton() {
  const btn = $("#btnBack");
  if (!btn) return;
  btn.hidden = !document.body.classList.contains("detailOpen");
}

function setMatch(next) {
  const m = ["all", "pn", "term"].includes(next) ? next : "all";
  currentMatch = m;
  document.querySelectorAll(".segBtn[data-filter]").forEach((btn) => {
    const on = btn.dataset.filter === m;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
}

function getTotalPages() {
  const t = Number(totalResults) || 0;
  return Math.max(1, Math.ceil(t / PAGE_SIZE));
}

function updatePagerUi() {
  const pages = getTotalPages();
  const info = $("#pagerInfo");
  if (info) info.textContent = `第 ${currentPage} / ${pages} 页`;

  const prev = $("#btnPrev");
  const next = $("#btnNext");
  if (prev) prev.disabled = currentPage <= 1;
  if (next) next.disabled = currentPage >= pages;

  const input = $("#pageInput");
  if (input) {
    input.value = String(currentPage);
    input.max = String(pages);
  }

  setPagerVisible((Number(totalResults) || 0) > PAGE_SIZE);
}

function matchesPn(r, q) {
  const needle = (q ?? "").toString().trim().toUpperCase();
  if (!needle) return false;
  const fields = [r?.part_number_canonical, r?.part_number_extracted, r?.part_number_cell];
  return fields.some((v) => (v ?? "").toString().toUpperCase().includes(needle));
}

function matchesTerm(r, q) {
  const needle = (q ?? "").toString().trim().toUpperCase();
  if (!needle) return false;
  const text = (r?.nomenclature_preview_raw || r?.nomenclature_preview || "").toString().toUpperCase();
  return text.includes(needle);
}

function renderResults(results) {
  const tokens = tokenizeQuery(lastQuery);
  const root = $("#results");
  root.innerHTML = "";
  if (!results.length) {
    root.innerHTML = `<div class="empty" style="margin:10px; opacity:.9">
      <div class="emptyTitle">暂无结果</div>
      <div class="emptyTips">
        <div class="tip">
          <div class="k">提示</div>
          <div class="v">可切换“术语匹配/全部”再试，或输入更完整的件号。</div>
        </div>
      </div>
    </div>`;
    return;
  }

  for (const r of results) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "card";
    card.dataset.id = String(r.id);

    const pn = fmtPn(r);
    const src = fmtSrc(r);
    const desc = (r.nomenclature_preview || "").toString();
    const level = Number(r.nom_level ?? 0) || 0;

    const row1 = document.createElement("div");
    row1.className = "row1";
    row1.innerHTML = `<div class="pnMini">${highlightHtml(pn || "—", tokens)}</div><div class="srcMini">${escapeHtml(
      src
    )}</div>`;

    const row2 = document.createElement("div");
    row2.className = "row2";
    row2.innerHTML = highlightHtml(desc || "", tokens);
    if (level > 0) {
      row2.style.paddingLeft = `${Math.min(level, 6) * 12}px`;
      row2.style.borderLeft = "2px solid rgba(0, 0, 0, 0.12)";
      row2.style.marginLeft = "2px";
    }

    if (SHOW_BADGES) {
      const badgeRow = document.createElement("div");
      badgeRow.className = "badges";

      if (r.not_illustrated) badgeRow.appendChild(badge("不可见", "warn"));
      if (r.pn_method) {
        const m = r.pn_method.toString();
        badgeRow.appendChild(badge(labelPnMethod(m), m === "unverified" ? "warn" : ""));
      }
      if (r.page_end && Number(r.page_end) !== Number(r.page_num)) badgeRow.appendChild(badge("跨页", ""));

      if (badgeRow.childElementCount) card.appendChild(badgeRow);
    }

    card.appendChild(row1);
    card.appendChild(row2);
    card.addEventListener("click", () => selectPart(r.id, card, { resetHistory: true }));
    root.appendChild(card);
  }
}

async function selectPart(id, cardEl, opts = {}) {
  if (!id) return;

  const resetHistory = Boolean(opts.resetHistory);
  const pushHistory = Boolean(opts.pushHistory);
  const fromBack = Boolean(opts.fromBack);
  const fromUrl = Boolean(opts.fromUrl);

  if (resetHistory) navStack = [];
  if (!fromBack && pushHistory && activeId && activeId !== id) navStack.push(activeId);

  activeId = id;
  document.body.classList.add("detailOpen");
  updateBackButton();
  if (!isRestoring) {
    writeUrlState({ q: lastQuery, id, page: currentPage, match: currentMatch }, { replace: fromBack || fromUrl });
  }

  const resultsRoot = $("#results");
  resultsRoot.querySelectorAll(".card.active").forEach((el) => el.classList.remove("active"));
  const toActivate = cardEl || resultsRoot.querySelector(`.card[data-id="${String(id)}"]`);
  toActivate?.classList.add("active");

  $("#emptyState").hidden = true;
  $("#detail").hidden = false;
  $("#pnSub").textContent = "";
  $("#desc").textContent = "加载中…";
  currentTermText = "";
  currentTermHas = { replace: false, optional: false };
  updateKeywordCards({ replace: null, optional: null });
  $("#previewHint").textContent = "正在加载预览…";
  $("#preview").removeAttribute("src");

  try {
    const detail = await fetchJson(`/api/part/${id}`);
    const p = detail.part;

    const pnMain = (p.pn || p.part_number_canonical || p.part_number_extracted || p.part_number_cell || "—").toString();
    $("#pnMain").textContent = pnMain;

    const badgesEl = $("#badges");
    badgesEl.innerHTML = "";
    badgesEl.hidden = !SHOW_BADGES;
    if (SHOW_BADGES) {
      if (p.not_illustrated) badgesEl.appendChild(badge("不可见", "warn"));
      if (p.pn_method) {
        const m = p.pn_method.toString();
        badgesEl.appendChild(badge(labelPnMethod(m), m === "unverified" ? "warn" : ""));
      }
    }

    $("#srcPdf").textContent = p.pdf || p.source_pdf || "—";
    const p1 = Number(p.page ?? p.page_num);
    const p2 = Number(p.page_end ?? p.page ?? p.page_num);
    $("#srcPage").textContent = p2 && p2 !== p1 ? `${p1}~${p2}` : `${p1}`;
    $("#srcFigure").textContent = p.fig || p.figure_code || p.figure_label || "—";
    $("#srcFigItem").textContent = p.fig_item || "—";
    $("#srcQty").textContent = fmtUnits(p.units ?? p.units_per_assy) || "—";
    $("#srcEff").textContent = p.eff || p.effectivity || "—";
    const metaLine = (p.meta_data_raw || "").toString().replace(/\s+/g, " ").trim();
    $("#srcMeta").textContent = metaLine || "—";
    const descFull = (p.nom || p.nomenclature_full || p.nom_clean || p.nomenclature_clean || p.nomenclature || "").toString().trim();
    currentTermText = descFull || "";
    currentTermHas = detectTermKeywords(currentTermText);
    renderTermDesc();

    // Hierarchy: only part numbers + jump history
    const hierRoot = $("#hier");
    hierRoot.innerHTML = "";

    const mkCol = (title, nodes) => {
      const col = document.createElement("div");
      col.className = "hierCol";

      const h = document.createElement("div");
      h.className = "hierTitle";
      h.textContent = title;

      const list = document.createElement("div");
      list.className = "hierItems";

      if (!nodes?.length) {
        const empty = document.createElement("div");
        empty.className = "hierEmpty";
        empty.textContent = "无";
        list.appendChild(empty);
      } else {
        for (const n of nodes) {
          const pn = (n?.pn || n?.part_number || "").toString().trim() || "—";
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "hierBtn";
          btn.textContent = pn;
          btn.addEventListener("click", () => selectPart(n.id, null, { pushHistory: true }));
          list.appendChild(btn);
        }
      }

      col.appendChild(h);
      col.appendChild(list);
      return col;
    };

    const anc = detail.parents ?? detail.hierarchy?.ancestors ?? [];
    const parent = anc.length ? anc[anc.length - 1] : null;
    const siblings = detail.siblings ?? detail.hierarchy?.siblings ?? [];
    const children = detail.children ?? detail.hierarchy?.children ?? [];

    hierRoot.appendChild(mkCol("父辈", parent ? [parent] : []));
    hierRoot.appendChild(mkCol("平辈", siblings.slice(0, 18)));
    hierRoot.appendChild(mkCol("子辈", children.slice(0, 24)));

    // Links + preview
    const pdfName = encodeURIComponent(p.pdf || p.source_pdf);
    const pageNum = Number(p.page ?? p.page_num);
    const pdfUrl = `/pdf/${pdfName}#page=${pageNum}`;
    const pageUrl = `/viewer.html?pdf=${pdfName}&page=${pageNum}`;
    const imgUrl = `/render/${pdfName}/${pageNum}.png?scale=2`;
    const btnOpenPage = $("#btnOpenPage");
    if (btnOpenPage) btnOpenPage.href = pageUrl;
    const btnOpenPdf = $("#btnOpenPdf");
    if (btnOpenPdf) btnOpenPdf.href = pdfUrl;

    const img = $("#preview");
    img.onload = () => {
      const hint =
        p2 && p2 !== p1
          ? `预览：${p.pdf || p.source_pdf} 第 ${pageNum} 页（跨页至 ${p2}）`
          : `预览：${p.pdf || p.source_pdf} 第 ${pageNum} 页`;
      $("#previewHint").textContent = hint;
    };
    img.onerror = () => {
      $("#previewHint").textContent = "预览加载失败（可点击“打开 PDF”重试）";
    };
    img.src = imgUrl;
  } catch (e) {
    $("#desc").textContent = `加载失败：${e?.message ?? e}`;
    currentTermText = "";
    currentTermHas = { replace: false, optional: false };
    updateKeywordCards({ replace: false, optional: false });
    $("#previewHint").textContent = "预览加载失败";
  }
}

async function doSearch(q, opts = {}) {
  clearActive();
  lastQuery = (q || "").toString().trim();
  hasSearched = Boolean(lastQuery);
  setResultsWrapVisible(false);
  totalResults = 0;
  setPagerVisible(false);

  if (!hasSearched) {
    setCount(0);
    setStatus("");
    setSearching(false);
    return;
  }

  currentPage =
    typeof opts?.page === "number" && Number.isFinite(opts.page) ? Math.max(1, Math.floor(opts.page)) : 1;
  setMatch(opts?.match ?? currentMatch);
  updatePagerUi();

  if (!isRestoring) writeUrlState({ q: lastQuery, id: null, page: currentPage, match: currentMatch }, { replace: true });

  const url = `/api/search?q=${encodeURIComponent(q)}&page=${currentPage}&page_size=${PAGE_SIZE}&match=${encodeURIComponent(
    currentMatch
  )}&include_notes=0`;
  setStatus("查询中…");
  setSearching(true);
  try {
    const data = await fetchJson(url);
    const serverMatchRaw = (data.match ?? "").toString().trim().toLowerCase();
    const serverHasPaging =
      typeof data?.total === "number" && typeof data?.page === "number" && typeof data?.page_size === "number";
    const serverHasMatch = Boolean(serverMatchRaw);
    const serverMatchMismatch = serverHasMatch && serverMatchRaw !== currentMatch;
    let results = data.results ?? [];
    let total = Number(data.total ?? data.total_count ?? data.count ?? results.length) || 0;

    // Backward-compatible guard: only fallback when server explicitly returns a mismatched match mode.
    if (serverMatchMismatch) {
      if (currentMatch === "pn") results = results.filter((r) => matchesPn(r, lastQuery));
      if (currentMatch === "term") results = results.filter((r) => matchesTerm(r, lastQuery));
      total = results.length;
    }

    totalResults = total;

    const pages = getTotalPages();
    if (!results.length && total > 0 && currentPage > pages && !opts._adjusted) {
      currentPage = pages;
      return doSearch(lastQuery, { page: currentPage, match: currentMatch, _adjusted: true });
    }

    if (total <= 0) {
      totalResults = 0;
      setCount(0);
      setStatus("暂无结果");
      setResultsWrapVisible(true);
      renderResults([]);
      updatePagerUi();
      return;
    }

    setResultsWrapVisible(true);
    setCount(results.length, serverHasPaging && !serverMatchMismatch ? total : null);
    renderResults(results);

    const elapsed = Number(data.elapsed_ms ?? 0) || 0;
    if (!serverHasPaging || serverMatchMismatch) {
      setStatus(
        "\u63d0\u793a\uff1a\u670d\u52a1\u7aef\u4e0d\u652f\u6301\u201c\u5206\u9875/\u5339\u914d\u7b5b\u9009\u201d\u63a5\u53e3\uff08\u53ef\u80fd\u662f\u542f\u52a8\u4e86 demo/web_server.py\uff09\uff0c\u5f53\u524d\u53ea\u5c55\u793a\u8fd4\u56de\u7684\u524d\u51e0\u6761\u7ed3\u679c\u3002"
      );
    } else {
      setStatus(`共 ${total} 条 · 第 ${currentPage}/${pages} 页 · ${elapsed}ms`);
    }
    updatePagerUi();
  } catch (e) {
    totalResults = 0;
    setCount(0, 0);
    $("#results").innerHTML = `<div class="empty" style="margin:10px">
      <div class="emptyTitle">查询失败</div>
      <div class="emptyTips"><div class="tip"><div class="k">错误</div><div class="v">${escapeHtml(
        e?.message ?? e
      )}</div></div></div></div>`;
    setStatus("查询失败");
    clearActive();
    updatePagerUi();
    setResultsWrapVisible(true);
  } finally {
    setSearching(false);
  }
}

function scheduleSearch(q) {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    if (!q.trim()) {
      setCount(0);
      $("#results").innerHTML = "";
      setStatus("");
      clearActive();
      hasSearched = false;
      currentPage = 1;
      totalResults = 0;
      setMatch("pn");
      setPagerVisible(false);
      setResultsWrapVisible(false);
      if (!isRestoring) writeUrlState({ q: "", id: null }, { replace: true });
      return;
    }
    if (q.trim() === lastQuery && hasSearched) return;
    currentPage = 1;
    doSearch(q.trim(), { page: 1, match: currentMatch });
  }, 260);
}

async function restoreFromUrl() {
  const { q, id, page, match } = readUrlState();
  isRestoring = true;
  try {
    $("#q").value = q || "";
    setMatch(match);
    currentPage = page;

    if (!q.trim()) {
      setCount(0);
      $("#results").innerHTML = "";
      setStatus("");
      clearActive();
      hasSearched = false;
      currentPage = 1;
      totalResults = 0;
      setMatch(match || "pn");
      setPagerVisible(false);
      setResultsWrapVisible(false);
      if (id) await selectPart(id, null, { fromUrl: true, resetHistory: true });
      return;
    }

    lastQuery = q.trim();
    await doSearch(lastQuery, { page: currentPage, match: currentMatch });
    if (id) await selectPart(id, null, { fromUrl: true, resetHistory: true });
  } finally {
    isRestoring = false;
  }
}

function wire() {
  $("#searchForm").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const q = $("#q").value;
    lastQuery = "";
    scheduleSearch(q);
  });

  $("#q").addEventListener("input", (ev) => scheduleSearch(ev.target.value));

  document.querySelectorAll(".segBtn[data-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const nextMatch = (btn.dataset.filter || "all").toString();
      const q = ($("#q")?.value || "").toString().trim();
      if (!q) return;
      if (nextMatch === currentMatch && hasSearched) return;
      currentPage = 1;
      doSearch(q, { page: 1, match: nextMatch });
    });
  });

  $("#btnPrev")?.addEventListener("click", () => {
    if (!hasSearched || currentPage <= 1) return;
    doSearch(lastQuery, { page: currentPage - 1, match: currentMatch });
  });

  $("#btnNext")?.addEventListener("click", () => {
    const pages = getTotalPages();
    if (!hasSearched || currentPage >= pages) return;
    doSearch(lastQuery, { page: currentPage + 1, match: currentMatch });
  });

  const jump = () => {
    const pages = getTotalPages();
    const raw = ($("#pageInput")?.value || "").toString();
    const n = /^\d+$/.test(raw) ? Number(raw) : NaN;
    if (!Number.isFinite(n)) return;
    const p = Math.min(Math.max(1, n), pages);
    if (p === currentPage) return;
    doSearch(lastQuery, { page: p, match: currentMatch });
  };

  $("#btnJump")?.addEventListener("click", jump);
  $("#pageInput")?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      jump();
    }
  });

  $("#btnBack")?.addEventListener("click", () => {
    if (navStack.length) {
      const prev = navStack.pop();
      if (prev) return selectPart(prev, null, { fromBack: true });
    }
    closeDetail({ updateUrl: true });
  });

  $("#dbChip")?.addEventListener("click", async () => {
    try {
      if (!docsCache) {
        await refreshDocsCache();
      }
    } catch {
      // ignore
    }
    openDocs();
  });

  $("#btnCloseDocs")?.addEventListener("click", closeDocs);
  $("#docsModal")?.addEventListener("click", (ev) => {
    const target = ev.target;
    if (target && target.matches("[data-close]")) closeDocs();
  });

  window.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape") return;
    if (!$("#docsModal")?.hidden) return closeDocs();
  });

  window.addEventListener("popstate", () => {
    restoreFromUrl();
  });

  $("#importForm")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fileInput = $("#importFile");
    const submitBtn = $("#btnImport");
    const file = fileInput?.files?.[0] ?? null;
    if (!file) {
      setImportStatus("请选择一个 PDF 文件", "bad");
      return;
    }
    try {
      if (submitBtn) submitBtn.disabled = true;
      await submitImportFile(file);
      if (fileInput) fileInput.value = "";
    } catch (e) {
      setImportStatus(`导入失败：${e?.message || e}`, "bad");
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

init();
wire();
restoreFromUrl();
