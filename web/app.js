const PAGE_SIZE = 60;

function $(sel, root = document) {
  return root.querySelector(sel);
}

function escapeHtml(s) {
  return (s ?? "")
    .toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toPositiveInt(v, fallback) {
  const n = Number.parseInt(String(v ?? ""), 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function normalizeDir(v) {
  const raw = (v ?? "").toString().replaceAll("\\", "/").trim().replace(/^\/+|\/+$/g, "");
  if (!raw) return "";
  return raw
    .split("/")
    .filter((x) => x && x !== "." && x !== "..")
    .join("/");
}

function searchStateFromUrl() {
  const params = new URLSearchParams(window.location.search || "");
  return {
    q: (params.get("q") || "").trim(),
    match: ["pn", "term", "all"].includes(params.get("match") || "") ? params.get("match") : "pn",
    page: toPositiveInt(params.get("page"), 1),
    include_notes: params.get("include_notes") === "1",
    source_dir: normalizeDir(params.get("source_dir") || ""),
    source_pdf: (params.get("source_pdf") || "").trim(),
  };
}

function buildSearchQuery(state) {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  params.set("match", state.match || "pn");
  params.set("page", String(toPositiveInt(state.page, 1)));
  params.set("page_size", String(PAGE_SIZE));
  if (state.include_notes) params.set("include_notes", "1");
  if (state.source_dir) params.set("source_dir", state.source_dir);
  if (state.source_pdf) params.set("source_pdf", state.source_pdf);
  return params;
}

function buildSearchPageUrl(state) {
  return `/search?${buildSearchQuery(state).toString()}`;
}

function contextParamsFromState(state) {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.match) params.set("match", state.match);
  if (state.page) params.set("page", String(state.page));
  if (state.include_notes) params.set("include_notes", "1");
  if (state.source_dir) params.set("source_dir", state.source_dir);
  if (state.source_pdf) params.set("source_pdf", state.source_pdf);
  return params;
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
  });

  let data = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }

  if (!res.ok) {
    const message = data?.message || `${res.status} ${res.statusText}`;
    throw new Error(message);
  }
  return data;
}

function loadStoredJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function saveStoredJson(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore local storage errors
  }
}

function initHomePage() {
  const form = $("#homeSearchForm");
  const input = $("#homeQ");
  if (!form || !input) return;

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const q = (input.value || "").trim();
    if (!q) {
      input.focus();
      return;
    }
    const params = new URLSearchParams();
    params.set("q", q);
    params.set("match", "pn");
    params.set("page", "1");
    window.location.href = `/search?${params.toString()}`;
  });
}

async function initSearchPage() {
  const form = $("#searchForm");
  const qInput = $("#searchQ");
  const matchSelect = $("#matchSelect");
  const includeNotes = $("#includeNotes");
  const dirSelect = $("#dirSelect");
  const docSelect = $("#docSelect");
  const summary = $("#resultSummary");
  const statusEl = $("#queryStatus");
  const tbody = $("#resultsBody");
  const empty = $("#emptyState");
  const prevBtn = $("#btnPrev");
  const nextBtn = $("#btnNext");
  const pagerInfo = $("#pagerInfo");
  const historyList = $("#historyList");
  const favoritesList = $("#favoritesList");

  if (!form || !qInput || !matchSelect || !includeNotes || !dirSelect || !docSelect || !tbody || !empty) return;

  let state = searchStateFromUrl();
  let docs = [];
  let total = 0;
  let historyItems = loadStoredJson("ipc_search_history", []);
  let favoriteItems = loadStoredJson("ipc_favorites", []);
  if (!Array.isArray(historyItems)) historyItems = [];
  if (!Array.isArray(favoriteItems)) favoriteItems = [];

  function applyStateToControls() {
    qInput.value = state.q;
    matchSelect.value = state.match;
    includeNotes.checked = Boolean(state.include_notes);
    dirSelect.value = state.source_dir || "";
    docSelect.value = state.source_pdf || "";
  }

  function populateDirOptions() {
    const dirs = new Set([""]);
    for (const d of docs) {
      const relDir = normalizeDir(d?.relative_dir || "");
      dirs.add(relDir);
    }
    const items = Array.from(dirs.values()).sort((a, b) => a.localeCompare(b));
    dirSelect.innerHTML = items
      .map((dir) => `<option value="${escapeHtml(dir)}">${dir || "全部目录"}</option>`)
      .join("");
    if (!items.includes(state.source_dir || "")) {
      state.source_dir = "";
    }
    dirSelect.value = state.source_dir || "";
  }

  function populateDocOptions() {
    const currentDir = state.source_dir || "";
    const list = docs.filter((d) => {
      const dir = normalizeDir(d?.relative_dir || "");
      return !currentDir || dir === currentDir;
    });

    const options = ['<option value="">全部文档</option>'];
    for (const d of list) {
      const rel = (d?.relative_path || d?.pdf_name || "").toString();
      const name = (d?.pdf_name || rel).toString();
      options.push(`<option value="${escapeHtml(rel)}">${escapeHtml(name)}</option>`);
    }
    docSelect.innerHTML = options.join("");

    if (state.source_pdf) {
      const ok = list.some((d) => {
        const rel = (d?.relative_path || d?.pdf_name || "").toString();
        return rel === state.source_pdf;
      });
      if (!ok) state.source_pdf = "";
    }
    docSelect.value = state.source_pdf || "";
  }

  async function loadFilters() {
    const payload = await fetchJson("/api/docs");
    docs = Array.isArray(payload) ? payload : payload?.documents || [];
    populateDirOptions();
    populateDocOptions();
  }

  function updateUrl() {
    const url = buildSearchPageUrl(state);
    history.replaceState({ ...state }, "", url);
  }

  function isFavorite(id) {
    return favoriteItems.some((x) => Number(x.id) === Number(id));
  }

  function saveFavorites() {
    saveStoredJson("ipc_favorites", favoriteItems.slice(0, 200));
  }

  function toggleFavorite(item) {
    const idx = favoriteItems.findIndex((x) => Number(x.id) === Number(item.id));
    if (idx >= 0) {
      favoriteItems.splice(idx, 1);
    } else {
      favoriteItems.unshift({
        id: Number(item.id),
        pn: item.part_number_canonical || item.part_number_cell || "-",
        source: item.source_relative_path || item.source_pdf || "-",
        page: Number(item.page_num || 0),
      });
      if (favoriteItems.length > 200) {
        favoriteItems = favoriteItems.slice(0, 200);
      }
    }
    saveFavorites();
    renderFavorites();
  }

  function pushHistory() {
    if (!state.q) return;
    const entry = {
      q: state.q,
      match: state.match,
      include_notes: Boolean(state.include_notes),
      source_dir: state.source_dir || "",
      source_pdf: state.source_pdf || "",
      ts: Date.now(),
    };
    const key = `${entry.q}|${entry.match}|${entry.include_notes ? 1 : 0}|${entry.source_dir}|${entry.source_pdf}`;
    historyItems = [entry, ...historyItems.filter((x) => `${x.q}|${x.match}|${x.include_notes ? 1 : 0}|${x.source_dir || ""}|${x.source_pdf || ""}` !== key)];
    if (historyItems.length > 30) historyItems = historyItems.slice(0, 30);
    saveStoredJson("ipc_search_history", historyItems);
    renderHistory();
  }

  function renderHistory() {
    if (!historyList) return;
    historyList.innerHTML = "";
    if (!historyItems.length) {
      historyList.innerHTML = '<div class="muted">暂无历史</div>';
      return;
    }
    for (const item of historyItems.slice(0, 12)) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "quickItem";
      const suffix = [item.match || "pn", item.source_dir || "", item.source_pdf || ""].filter(Boolean).join(" · ");
      btn.textContent = suffix ? `${item.q} (${suffix})` : item.q;
      btn.addEventListener("click", async () => {
        state = {
          q: (item.q || "").toString(),
          match: ["pn", "term", "all"].includes(item.match) ? item.match : "pn",
          page: 1,
          include_notes: Boolean(item.include_notes),
          source_dir: normalizeDir(item.source_dir || ""),
          source_pdf: (item.source_pdf || "").toString(),
        };
        applyStateToControls();
        populateDocOptions();
        await runSearch();
      });
      historyList.appendChild(btn);
    }
  }

  function renderFavorites() {
    if (!favoritesList) return;
    favoritesList.innerHTML = "";
    if (!favoriteItems.length) {
      favoritesList.innerHTML = '<div class="muted">暂无收藏</div>';
      return;
    }
    for (const item of favoriteItems.slice(0, 20)) {
      const a = document.createElement("a");
      a.className = "quickItem";
      const ctx = contextParamsFromState(state).toString();
      a.href = `/part/${encodeURIComponent(String(item.id))}${ctx ? `?${ctx}` : ""}`;
      a.textContent = `${item.pn} · ${item.source} p.${item.page || "-"}`;
      favoritesList.appendChild(a);
    }
  }

  function renderResults(results) {
    tbody.innerHTML = "";
    if (!results.length) {
      empty.hidden = false;
      return;
    }

    empty.hidden = true;
    const ctx = contextParamsFromState(state).toString();
    for (const r of results) {
      const tr = document.createElement("tr");
      tr.className = "resultRow";
      const favored = isFavorite(r.id);
      tr.innerHTML = `
        <td><button class="starBtn ${favored ? "on" : ""}" type="button">${favored ? "★" : "☆"}</button></td>
        <td class="mono">${escapeHtml(r.part_number_canonical || r.part_number_cell || "-")}</td>
        <td>${escapeHtml(r.source_relative_path || r.source_pdf || "-")}</td>
        <td class="mono">${escapeHtml(String(r.page_num ?? "-"))}</td>
        <td>${escapeHtml(r.nomenclature_preview || "")}</td>
      `;
      tr.querySelector(".starBtn")?.addEventListener("click", (ev) => {
        ev.stopPropagation();
        toggleFavorite(r);
        renderResults(results);
      });
      tr.addEventListener("click", () => {
        const target = `/part/${encodeURIComponent(String(r.id))}${ctx ? `?${ctx}` : ""}`;
        window.location.href = target;
      });
      tbody.appendChild(tr);
    }
  }

  async function runSearch() {
    if (!state.q) {
      tbody.innerHTML = "";
      empty.hidden = false;
      if (summary) summary.textContent = "请输入查询词";
      if (statusEl) statusEl.textContent = "";
      return;
    }

    updateUrl();
    if (statusEl) statusEl.textContent = "查询中...";
    const params = buildSearchQuery(state);
    try {
      const data = await fetchJson(`/api/search?${params.toString()}`);
      const results = Array.isArray(data?.results) ? data.results : [];
      total = Number(data?.total || 0);
      const pageSize = Number(data?.page_size || PAGE_SIZE) || PAGE_SIZE;
      const pages = Math.max(1, Math.ceil(total / pageSize));
      state.page = Math.min(state.page, pages);

      renderResults(results);
      pushHistory();
      if (summary) summary.textContent = `总计 ${total} 条`;
      if (pagerInfo) pagerInfo.textContent = `第 ${state.page} / ${pages} 页`;
      if (statusEl) statusEl.textContent = `match=${data?.match || state.match}`;
      if (prevBtn) prevBtn.disabled = state.page <= 1;
      if (nextBtn) nextBtn.disabled = state.page >= pages;
    } catch (e) {
      tbody.innerHTML = "";
      empty.hidden = false;
      if (summary) summary.textContent = "查询失败";
      if (statusEl) statusEl.textContent = String(e?.message || e);
    }
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    state.q = (qInput.value || "").trim();
    state.match = matchSelect.value || "pn";
    state.include_notes = includeNotes.checked;
    state.source_dir = normalizeDir(dirSelect.value || "");
    state.source_pdf = (docSelect.value || "").trim();
    state.page = 1;
    await runSearch();
  });

  dirSelect.addEventListener("change", () => {
    state.source_dir = normalizeDir(dirSelect.value || "");
    state.source_pdf = "";
    populateDocOptions();
  });

  docSelect.addEventListener("change", () => {
    state.source_pdf = (docSelect.value || "").trim();
  });

  prevBtn?.addEventListener("click", async () => {
    if (state.page <= 1) return;
    state.page -= 1;
    await runSearch();
  });

  nextBtn?.addEventListener("click", async () => {
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (state.page >= pages) return;
    state.page += 1;
    await runSearch();
  });

  applyStateToControls();
  await loadFilters();
  renderHistory();
  renderFavorites();
  await runSearch();
}

function renderHierarchyLinks(el, items, state) {
  if (!el) return;
  el.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    el.innerHTML = '<div class="muted">无</div>';
    return;
  }
  const qs = contextParamsFromState(state).toString();
  for (const item of items) {
    const a = document.createElement("a");
    a.className = "linkBtn";
    a.href = `/part/${encodeURIComponent(String(item.id))}${qs ? `?${qs}` : ""}`;
    a.textContent = item?.pn || item?.part_number || "-";
    el.appendChild(a);
  }
}

async function initDetailPage() {
  const m = window.location.pathname.match(/^\/part\/(\d+)$/);
  if (!m) return;
  const id = Number(m[1]);
  if (!Number.isFinite(id)) return;

  const state = searchStateFromUrl();
  const back = $("#backToResults");
  if (back) back.href = buildSearchPageUrl(state);

  try {
    const data = await fetchJson(`/api/part/${id}`);
    const p = data?.part || {};
    const pn = (p.pn || p.part_number_canonical || p.part_number_cell || "-").toString();
    const pdf = (p.pdf || p.source_pdf || "").toString();
    const page = Number(p.page || p.page_num || 1);
    const pageEnd = Number(p.page_end || page);

    $("#partPn").textContent = pn;
    $("#partMeta").textContent = `${pdf || "-"} · 页 ${page}${pageEnd !== page ? `~${pageEnd}` : ""}`;
    $("#srcPath").textContent = pdf || "-";
    $("#srcPage").textContent = pageEnd !== page ? `${page}~${pageEnd}` : String(page);
    $("#srcFigure").textContent = (p.fig || p.figure_code || "-").toString();
    $("#srcItem").textContent = (p.fig_item || "-").toString();
    $("#srcQty").textContent = (p.units || p.units_per_assy || "-").toString();
    $("#srcEff").textContent = (p.eff || p.effectivity || "-").toString();
    $("#partDesc").textContent = (p.nom || p.nomenclature || p.nomenclature_clean || "-").toString();

    const pdfEnc = encodeURIComponent(pdf);
    const openPage = $("#openPage");
    const openPdf = $("#openPdf");
    if (openPage) openPage.href = `/viewer.html?pdf=${pdfEnc}&page=${page}`;
    if (openPdf) openPdf.href = `/pdf/${pdfEnc}#page=${page}`;

    const preview = $("#previewImg");
    const hint = $("#previewHint");
    if (preview) {
      preview.src = `/render/${pdfEnc}/${page}.png`;
      preview.onload = () => {
        if (hint) hint.textContent = `${pdf} 第 ${page} 页`;
      };
      preview.onerror = () => {
        if (hint) hint.textContent = "预览加载失败";
      };
    }

    renderHierarchyLinks($("#parents"), data?.parents || [], state);
    renderHierarchyLinks($("#siblings"), data?.siblings || [], state);
    renderHierarchyLinks($("#children"), data?.children || [], state);
  } catch (e) {
    $("#partDesc").textContent = `加载失败：${e?.message || e}`;
  }
}

function normalizeDbPathFromUrl() {
  const params = new URLSearchParams(window.location.search || "");
  return normalizeDir(params.get("path") || "");
}

function buildDbUrl(path) {
  const p = normalizeDir(path || "");
  if (!p) return "/db";
  return `/db?path=${encodeURIComponent(p)}`;
}

function formatJobStatus(job) {
  const status = (job?.status || "").toString();
  if (status === "success") return "success";
  if (status === "failed") return "failed";
  if (status === "running") return "running";
  return "queued";
}

async function initDbPage() {
  const statusEl = $("#dbStatus");
  const crumbEl = $("#pathCrumb");
  const dirList = $("#dirList");
  const fileList = $("#fileList");
  const folderForm = $("#folderForm");
  const folderName = $("#folderName");
  const uploadForm = $("#uploadForm");
  const uploadFiles = $("#uploadFiles");
  const jobsList = $("#jobsList");
  const btnRescan = $("#btnRescan");

  if (!statusEl || !crumbEl || !dirList || !fileList || !folderForm || !folderName || !uploadForm || !uploadFiles || !jobsList) {
    return;
  }

  let currentPath = normalizeDbPathFromUrl();
  const activeImportJobs = new Set();
  let pollTimer = null;
  let activeScanJobId = "";

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function addJobRow(job, kind = "import") {
    const rowId = `${kind}-${job.job_id}`;
    let row = document.getElementById(rowId);
    if (!row) {
      row = document.createElement("div");
      row.id = rowId;
      row.className = "jobRow";
      jobsList.prepend(row);
    }

    const status = formatJobStatus(job);
    row.innerHTML = `
      <div>
        <div class="mono">${escapeHtml(job.relative_path || job.filename || job.path || "-")}</div>
        <div class="muted">${escapeHtml(kind)} · ${escapeHtml(status)}</div>
      </div>
      <span class="badge ${status === "success" ? "ok" : status === "failed" ? "bad" : ""}">${escapeHtml(status)}</span>
    `;
  }

  function ensurePolling() {
    if (pollTimer) return;
    pollTimer = setInterval(async () => {
      const done = [];
      for (const jobId of activeImportJobs.values()) {
        try {
          const job = await fetchJson(`/api/import/${encodeURIComponent(jobId)}`);
          addJobRow(job, "import");
          if (["success", "failed"].includes(job.status || "")) {
            done.push(jobId);
          }
        } catch {
          done.push(jobId);
        }
      }
      for (const jobId of done) activeImportJobs.delete(jobId);

      if (activeScanJobId) {
        try {
          const scanJob = await fetchJson(`/api/scan/${encodeURIComponent(activeScanJobId)}`);
          addJobRow(scanJob, "scan");
          if (["success", "failed"].includes(scanJob.status || "")) {
            activeScanJobId = "";
          }
        } catch {
          activeScanJobId = "";
        }
      }

      if (activeImportJobs.size === 0 && !activeScanJobId) {
        clearInterval(pollTimer);
        pollTimer = null;
        await loadTree(currentPath);
      }
    }, 1500);
  }

  function renderCrumb(path) {
    const parts = path ? path.split("/") : [];
    const nodes = ['<a href="/db">/</a>'];
    let acc = "";
    for (const part of parts) {
      acc = acc ? `${acc}/${part}` : part;
      nodes.push(`<span>/</span><a href="${buildDbUrl(acc)}">${escapeHtml(part)}</a>`);
    }
    crumbEl.innerHTML = nodes.join("");
    crumbEl.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        const href = a.getAttribute("href") || "/db";
        history.pushState({}, "", href);
        currentPath = normalizeDbPathFromUrl();
        loadTree(currentPath);
      });
    });
  }

  async function loadTree(path) {
    setStatus("加载中...");
    try {
      const payload = await fetchJson(`/api/docs/tree?path=${encodeURIComponent(path || "")}`);
      currentPath = normalizeDir(payload?.path || "");
      renderCrumb(currentPath);

      const dirs = Array.isArray(payload?.directories) ? payload.directories : [];
      const files = Array.isArray(payload?.files) ? payload.files : [];

      dirList.innerHTML = "";
      if (dirs.length) {
        for (const d of dirs) {
          const row = document.createElement("div");
          row.className = "dirRow";
          row.innerHTML = `
            <div class="pathLink">📁 ${escapeHtml(d.name || "")}</div>
            <button class="btn ghost" type="button">进入</button>
          `;
          row.querySelector("button")?.addEventListener("click", () => {
            const next = normalizeDir(d.path || "");
            history.pushState({}, "", buildDbUrl(next));
            loadTree(next);
          });
          dirList.appendChild(row);
        }
      } else {
        dirList.innerHTML = '<div class="muted">无子目录</div>';
      }

      fileList.innerHTML = "";
      if (files.length) {
        for (const f of files) {
          const row = document.createElement("div");
          row.className = "fileRow";
          const indexed = Boolean(f.indexed);
          row.innerHTML = `
            <div>
              <div class="pathLink">${escapeHtml(f.relative_path || f.name || "")}</div>
              <div class="muted">${indexed ? "已入库" : "未入库"}</div>
            </div>
            <div class="row gap">
              <span class="badge ${indexed ? "ok" : ""}">${indexed ? "indexed" : "pending"}</span>
              <button class="btn ghost" type="button">删除</button>
            </div>
          `;
          const delBtn = row.querySelector("button");
          delBtn?.addEventListener("click", async () => {
            const rel = (f.relative_path || f.name || "").toString();
            if (!rel) return;
            const ok = window.confirm(`确认删除 ${rel} ?\n将删除数据库记录和磁盘文件。`);
            if (!ok) return;
            try {
              await fetchJson(`/api/docs?name=${encodeURIComponent(rel)}`, { method: "DELETE" });
              await loadTree(currentPath);
            } catch (e) {
              setStatus(`删除失败：${e?.message || e}`);
            }
          });
          fileList.appendChild(row);
        }
      } else {
        fileList.innerHTML = '<div class="muted">无 PDF 文件</div>';
      }

      setStatus(`目录 ${currentPath || "/"} · 文件 ${files.length}`);
    } catch (e) {
      setStatus(`加载失败：${e?.message || e}`);
      dirList.innerHTML = "";
      fileList.innerHTML = "";
    }
  }

  window.addEventListener("popstate", () => {
    currentPath = normalizeDbPathFromUrl();
    loadTree(currentPath);
  });

  folderForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const name = (folderName.value || "").trim();
    if (!name) return;
    try {
      await fetchJson("/api/folders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: currentPath, name }),
      });
      folderName.value = "";
      await loadTree(currentPath);
    } catch (e) {
      setStatus(`创建失败：${e?.message || e}`);
    }
  });

  uploadForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const files = Array.from(uploadFiles.files || []);
    if (files.length === 0) {
      setStatus("请选择 PDF 文件");
      return;
    }
    setStatus(`准备上传 ${files.length} 个文件...`);

    for (const file of files) {
      try {
        const res = await fetch(`/api/import?filename=${encodeURIComponent(file.name)}&target_dir=${encodeURIComponent(currentPath)}`, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": file.type || "application/pdf",
            "X-File-Name": file.name,
            "X-Target-Dir": currentPath,
          },
          body: file,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data?.message || `${res.status} ${res.statusText}`);
        activeImportJobs.add(String(data.job_id));
        addJobRow(data, "import");
      } catch (e) {
        const fakeJob = {
          job_id: `error-${Date.now()}`,
          filename: file.name,
          status: "failed",
          error: String(e?.message || e),
        };
        addJobRow(fakeJob, "import");
      }
    }

    uploadFiles.value = "";
    ensurePolling();
  });

  btnRescan?.addEventListener("click", async () => {
    try {
      const job = await fetchJson(`/api/scan?path=${encodeURIComponent(currentPath)}`, { method: "POST" });
      activeScanJobId = String(job.job_id || "");
      if (activeScanJobId) {
        addJobRow(job, "scan");
        ensurePolling();
      }
    } catch (e) {
      setStatus(`触发重扫失败：${e?.message || e}`);
    }
  });

  await loadTree(currentPath);
}

function bootstrap() {
  const page = (document.body?.dataset?.page || "").toString();
  if (page === "home") {
    initHomePage();
    return;
  }
  if (page === "search") {
    initSearchPage();
    return;
  }
  if (page === "detail") {
    initDetailPage();
    return;
  }
  if (page === "db") {
    initDbPage();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}
