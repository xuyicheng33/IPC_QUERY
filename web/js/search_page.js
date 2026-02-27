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
  let effectivePageSize = PAGE_SIZE;
  let historyItems = loadStoredJson("ipc_search_history", []);
  let favoriteItems = loadStoredJson("ipc_favorites", []);
  if (!Array.isArray(historyItems)) historyItems = [];
  if (!Array.isArray(favoriteItems)) favoriteItems = [];
  const paginationUtils = (typeof window !== "undefined" && window.IpcSearchPaginationUtils)
    ? window.IpcSearchPaginationUtils
    : {
      toPositiveInt(value, fallback) {
        const parsed = Number.parseInt(String(value ?? ""), 10);
        if (Number.isFinite(parsed) && parsed > 0) {
          return parsed;
        }
        return Math.max(1, Number.parseInt(String(fallback ?? 1), 10) || 1);
      },
      resolvePageSize(value, fallbackPageSize) {
        return this.toPositiveInt(value, fallbackPageSize);
      },
      computeTotalPages(totalValue, pageSizeValue) {
        const totalSafe = Math.max(0, Number(totalValue) || 0);
        const sizeSafe = Math.max(1, this.toPositiveInt(pageSizeValue, 1));
        return Math.max(1, Math.ceil(totalSafe / sizeSafe));
      },
      clampPage(pageValue, totalPagesValue) {
        const pageSafe = this.toPositiveInt(pageValue, 1);
        const pagesSafe = Math.max(1, this.toPositiveInt(totalPagesValue, 1));
        return Math.min(pageSafe, pagesSafe);
      },
      shouldRefetchForClampedPage(requestedPage, clampedPage, totalValue) {
        const requested = this.toPositiveInt(requestedPage, 1);
        const clamped = this.toPositiveInt(clampedPage, 1);
        const totalSafe = Math.max(0, Number(totalValue) || 0);
        return totalSafe > 0 && requested !== clamped;
      },
    };

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
      const notesTag = item.include_notes ? "含备注" : "不含备注";
      const suffix = [item.match || "pn", notesTag, item.source_dir || "", item.source_pdf || ""].filter(Boolean).join(" · ");
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
    try {
      const requestedPage = state.page;
      let params = buildSearchQuery(state);
      let data = await fetchJson(`/api/search?${params.toString()}`);
      let results = Array.isArray(data?.results) ? data.results : [];
      total = Math.max(0, Number(data?.total || 0));
      effectivePageSize = paginationUtils.resolvePageSize(data?.page_size, PAGE_SIZE);
      let pages = paginationUtils.computeTotalPages(total, effectivePageSize);
      const clampedPage = paginationUtils.clampPage(requestedPage, pages);

      if (paginationUtils.shouldRefetchForClampedPage(requestedPage, clampedPage, total)) {
        state.page = clampedPage;
        updateUrl();
        params = buildSearchQuery(state);
        data = await fetchJson(`/api/search?${params.toString()}`);
        results = Array.isArray(data?.results) ? data.results : [];
        total = Math.max(0, Number(data?.total || 0));
        effectivePageSize = paginationUtils.resolvePageSize(data?.page_size, PAGE_SIZE);
        pages = paginationUtils.computeTotalPages(total, effectivePageSize);
      }

      state.page = paginationUtils.clampPage(state.page, pages);

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
    const pages = paginationUtils.computeTotalPages(total, effectivePageSize);
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
