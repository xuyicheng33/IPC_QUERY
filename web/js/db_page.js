async function initDbPage() {
  const statusEl = $("#dbStatus");
  const crumbEl = $("#pathCrumb");
  const treeRoot = $("#treeRoot");
  const fileBody = $("#dbFilesBody");
  const emptyEl = $("#dbEmpty");
  const actionResultEl = $("#dbActionResult");
  const selectAllBox = $("#selectAllFiles");
  const btnDeleteSelected = $("#btnDeleteSelected");
  const btnUpload = $("#btnUpload");
  const uploadFiles = $("#uploadFiles");
  const btnRefresh = $("#btnRefresh");
  const btnRefreshTree = $("#btnRefreshTree");
  const btnRescan = $("#btnRescan");
  const folderForm = $("#folderForm");
  const folderName = $("#folderName");
  const jobsList = $("#jobsList");

  if (
    !statusEl
    || !crumbEl
    || !treeRoot
    || !fileBody
    || !emptyEl
    || !actionResultEl
    || !selectAllBox
    || !btnDeleteSelected
    || !btnUpload
    || !uploadFiles
    || !btnRefresh
    || !btnRefreshTree
    || !btnRescan
    || !folderForm
    || !folderName
    || !jobsList
  ) {
    return;
  }

  let currentPath = normalizeDbPathFromUrl();
  let currentFiles = [];
  const selectedPaths = new Set();
  const treeCache = new Map();
  const expandedDirs = new Set([""]);
  const activeImportJobs = new Set();
  let activeScanJobId = "";
  const jobStatusByPath = new Map();
  let pollTimer = null;

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function setActionResult(text, isError = false) {
    actionResultEl.textContent = text || "";
    actionResultEl.classList.toggle("actionResultBad", Boolean(isError));
  }

  function upsertJobRow(job, kind = "import") {
    const rowId = `${kind}-${job.job_id}`;
    let row = document.getElementById(rowId);
    if (!row) {
      row = document.createElement("div");
      row.id = rowId;
      row.className = "jobRow";
      jobsList.prepend(row);
    }

    const status = formatJobStatus(job);
    const pathText = (job.relative_path || job.filename || job.path || "-").toString();
    const err = (job.error || "").toString();
    if (kind === "import" && pathText && pathText !== "-") {
      jobStatusByPath.set(pathText, status);
    }
    row.innerHTML = `
      <div>
        <div class="mono">${escapeHtml(pathText)}</div>
        <div class="muted">${escapeHtml(kind)} · ${escapeHtml(status)}</div>
        ${err ? `<div class="muted">${escapeHtml(err)}</div>` : ""}
      </div>
      <span class="badge ${status === "success" ? "ok" : status === "failed" ? "bad" : ""}">${escapeHtml(status)}</span>
    `;
  }

  async function ensureTreeNode(path, force = false) {
    const key = normalizeDir(path || "");
    if (!force && treeCache.has(key)) {
      return treeCache.get(key);
    }
    const payload = await fetchJson(`/api/docs/tree?path=${encodeURIComponent(key)}`);
    const node = {
      path: normalizeDir(payload?.path || key),
      directories: Array.isArray(payload?.directories) ? payload.directories : [],
      files: Array.isArray(payload?.files) ? payload.files : [],
    };
    treeCache.set(node.path, node);
    if (node.path !== key) {
      treeCache.set(key, node);
    }
    return node;
  }

  async function preloadPathChain(path, force = false) {
    const target = normalizeDir(path || "");
    await ensureTreeNode("", force);
    if (!target) return;
    let acc = "";
    for (const seg of target.split("/")) {
      acc = acc ? `${acc}/${seg}` : seg;
      await ensureTreeNode(acc, force);
    }
  }

  function pruneSelection(files) {
    const visible = new Set(
      (Array.isArray(files) ? files : []).map((f) => normalizeDir((f?.relative_path || f?.name || "").toString()))
    );
    for (const path of Array.from(selectedPaths.values())) {
      if (!visible.has(path)) {
        selectedPaths.delete(path);
      }
    }
  }

  function updateSelectSummary() {
    const count = selectedPaths.size;
    btnDeleteSelected.disabled = count === 0;
    btnDeleteSelected.textContent = count > 0 ? `删除所选 (${count})` : "删除所选";
  }

  function toggleSelection(path) {
    const rel = normalizeDir(path || "");
    if (!rel) return;
    if (selectedPaths.has(rel)) {
      selectedPaths.delete(rel);
    } else {
      selectedPaths.add(rel);
    }
    renderFileTable(currentFiles);
  }

  function toggleSelectAll(checked) {
    if (checked) {
      for (const f of currentFiles) {
        const rel = normalizeDir((f?.relative_path || f?.name || "").toString());
        if (rel) selectedPaths.add(rel);
      }
    } else {
      selectedPaths.clear();
    }
    renderFileTable(currentFiles);
  }

  function renderFileTable(files) {
    currentFiles = Array.isArray(files) ? files : [];
    pruneSelection(currentFiles);
    fileBody.innerHTML = "";
    emptyEl.hidden = currentFiles.length > 0;

    if (currentFiles.length === 0) {
      selectAllBox.checked = false;
      selectAllBox.disabled = true;
      updateSelectSummary();
      return;
    }

    selectAllBox.disabled = false;
    const checkedCount = currentFiles.filter((f) => {
      const rel = normalizeDir((f?.relative_path || f?.name || "").toString());
      return rel && selectedPaths.has(rel);
    }).length;
    selectAllBox.checked = checkedCount > 0 && checkedCount === currentFiles.length;

    for (const f of currentFiles) {
      const rel = normalizeDir((f?.relative_path || f?.name || "").toString());
      const indexed = Boolean(f?.indexed);
      const taskStatus = jobStatusByPath.get(rel) || "-";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><input type="checkbox" ${selectedPaths.has(rel) ? "checked" : ""} ${rel ? "" : "disabled"} /></td>
        <td class="filePath">${escapeHtml(rel || "-")}</td>
        <td><span class="badge ${indexed ? "ok" : ""}">${indexed ? "indexed" : "pending"}</span></td>
        <td><span class="badge ${taskStatus === "success" ? "ok" : taskStatus === "failed" ? "bad" : ""}">${escapeHtml(taskStatus)}</span></td>
        <td><button class="btn ghost" type="button" ${rel ? "" : "disabled"}>删除</button></td>
      `;
      tr.querySelector('input[type="checkbox"]')?.addEventListener("change", () => toggleSelection(rel));
      tr.querySelector("button")?.addEventListener("click", async () => {
        if (!rel) return;
        await deleteSelected([rel]);
      });
      fileBody.appendChild(tr);
    }
    updateSelectSummary();
  }

  function renderCrumb(path) {
    const parts = path ? path.split("/") : [];
    const nodes = ['<a href="/db" data-path="">/</a>'];
    let acc = "";
    for (const part of parts) {
      acc = acc ? `${acc}/${part}` : part;
      nodes.push(`<span>/</span><a href="${buildDbUrl(acc)}" data-path="${escapeHtml(acc)}">${escapeHtml(part)}</a>`);
    }
    crumbEl.innerHTML = nodes.join("");
    crumbEl.querySelectorAll("a[data-path]").forEach((a) => {
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        const next = normalizeDir(a.getAttribute("data-path") || "");
        void loadDirectory(next, { push: true, force: false });
      });
    });
  }

  function appendPdfLeaves(path, depth) {
    const node = treeCache.get(path);
    if (!node) return;
    for (const f of node.files || []) {
      const rel = (f?.relative_path || f?.name || "").toString();
      const leaf = document.createElement("div");
      leaf.className = "treeLeaf";
      leaf.style.paddingLeft = `${depth * 14}px`;
      leaf.textContent = `📄 ${rel || "-"}`;
      treeRoot.appendChild(leaf);
    }
  }

  function renderTreeNode(path, depth) {
    const node = treeCache.get(path);
    if (!node) return;
    for (const d of node.directories || []) {
      const dirPath = normalizeDir(d?.path || "");
      const expanded = expandedDirs.has(dirPath);
      const row = document.createElement("div");
      row.className = `treeRow ${dirPath === currentPath ? "active" : ""}`;
      row.style.paddingLeft = `${depth * 14}px`;
      row.innerHTML = `
        <button class="treeToggle" type="button">${expanded ? "▾" : "▸"}</button>
        <button class="treeDirBtn" type="button">📁 ${escapeHtml((d?.name || dirPath || "").toString())}</button>
      `;
      row.querySelector(".treeToggle")?.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        if (expandedDirs.has(dirPath)) {
          expandedDirs.delete(dirPath);
          renderTree();
          return;
        }
        expandedDirs.add(dirPath);
        try {
          await ensureTreeNode(dirPath);
          renderTree();
        } catch (e) {
          setStatus(`目录加载失败：${e?.message || e}`);
        }
      });
      row.querySelector(".treeDirBtn")?.addEventListener("click", () => {
        void loadDirectory(dirPath, { push: true, force: false });
      });
      treeRoot.appendChild(row);

      if (expandedDirs.has(dirPath)) {
        appendPdfLeaves(dirPath, depth + 1);
        renderTreeNode(dirPath, depth + 1);
      }
    }
  }

  function renderTree() {
    treeRoot.innerHTML = "";
    const rootRow = document.createElement("div");
    rootRow.className = `treeRow ${currentPath === "" ? "active" : ""}`;
    rootRow.style.paddingLeft = "0px";
    rootRow.innerHTML = `<button class="treeDirBtn" type="button">📁 /</button>`;
    rootRow.querySelector(".treeDirBtn")?.addEventListener("click", () => {
      void loadDirectory("", { push: true, force: false });
    });
    treeRoot.appendChild(rootRow);

    appendPdfLeaves("", 1);
    renderTreeNode("", 1);
  }

  async function loadDirectory(path, options = {}) {
    const { push = false, force = false } = options;
    const target = normalizeDir(path || "");
    setStatus("加载中...");
    try {
      await preloadPathChain(target, force);
      const payload = await ensureTreeNode(target, force);
      currentPath = normalizeDir(payload?.path || target);

      expandedDirs.add("");
      if (currentPath) {
        let acc = "";
        for (const seg of currentPath.split("/")) {
          acc = acc ? `${acc}/${seg}` : seg;
          expandedDirs.add(acc);
        }
      }

      renderCrumb(currentPath);
      renderTree();
      renderFileTable(payload?.files || []);
      if (push) {
        history.pushState({}, "", buildDbUrl(currentPath));
      }
      setStatus(`目录 ${currentPath || "/"} · 文件 ${currentFiles.length}`);
    } catch (e) {
      setStatus(`加载失败：${e?.message || e}`);
      renderFileTable([]);
    }
  }

  async function refreshCurrentDirectory() {
    await loadDirectory(currentPath, { push: false, force: true });
  }

  function ensurePolling() {
    if (pollTimer) return;
    pollTimer = setInterval(async () => {
      const done = [];
      for (const jobId of activeImportJobs.values()) {
        try {
          const job = await fetchJson(`/api/import/${encodeURIComponent(jobId)}`);
          upsertJobRow(job, "import");
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
          upsertJobRow(scanJob, "scan");
          if (["success", "failed"].includes(scanJob.status || "")) {
            activeScanJobId = "";
          }
        } catch {
          activeScanJobId = "";
        }
      }

      renderFileTable(currentFiles);
      if (activeImportJobs.size === 0 && !activeScanJobId) {
        clearInterval(pollTimer);
        pollTimer = null;
        await refreshCurrentDirectory();
      }
    }, 1500);
  }

  function formatFailedSummary(payload) {
    const results = Array.isArray(payload?.results) ? payload.results : [];
    const failed = results.filter((r) => !r?.ok);
    if (failed.length === 0) return "";
    const sample = failed.slice(0, 3).map((r) => {
      const path = (r?.path || "-").toString();
      const code = (r?.error_code || "").toString().toUpperCase();
      if (code === "CONFLICT") {
        const candidates = Array.isArray(r?.details?.candidates)
          ? r.details.candidates.slice(0, 3).join(", ")
          : "";
        const suffix = candidates ? `，候选: ${candidates}` : "";
        return `${path}: 命名冲突，请使用完整相对路径${suffix}`;
      }
      return `${path}: ${r?.error || "unknown error"}`;
    });
    return sample.join(" | ");
  }

  async function deleteSelected(paths) {
    const list = Array.isArray(paths) ? paths.map((p) => normalizeDir(p || "")).filter(Boolean) : [];
    if (list.length === 0) return;
    const sample = list.slice(0, 5).join("\n");
    const tail = list.length > 5 ? "\n..." : "";
    const ok = window.confirm(
      `确认删除 ${list.length} 个文件？\n将删除数据库记录和磁盘文件。\n\n示例路径：\n${sample}${tail}`
    );
    if (!ok) return;

    setStatus(`正在删除 ${list.length} 个文件...`);
    setActionResult("");
    try {
      const payload = await fetchJson("/api/docs/batch-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paths: list }),
      });
      const failedSummary = formatFailedSummary(payload);
      setActionResult(
        failedSummary
          ? `删除完成：成功 ${payload.deleted}/${payload.total}，失败 ${payload.failed}（${failedSummary}）`
          : `删除完成：成功 ${payload.deleted}/${payload.total}，失败 ${payload.failed}`
      );
      selectedPaths.clear();
      await refreshCurrentDirectory();
    } catch (e) {
      setActionResult(`删除失败：${e?.message || e}`, true);
      setStatus(`删除失败：${e?.message || e}`);
    }
  }

  async function submitUploads(files) {
    if (!Array.isArray(files) || files.length === 0) {
      setStatus("请选择 PDF 文件");
      return;
    }
    setStatus(`准备上传 ${files.length} 个文件...`);
    setActionResult("");

    for (const file of files) {
      try {
        const res = await fetch(
          `/api/import?filename=${encodeURIComponent(file.name)}&target_dir=${encodeURIComponent(currentPath)}`,
          {
            method: "POST",
            headers: {
              Accept: "application/json",
              "Content-Type": file.type || "application/pdf",
              "X-File-Name": file.name,
              "X-Target-Dir": currentPath,
            },
            body: file,
          }
        );
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data?.message || `${res.status} ${res.statusText}`);
        activeImportJobs.add(String(data.job_id));
        upsertJobRow(data, "import");
      } catch (e) {
        const fakeJob = {
          job_id: `error-${Date.now()}`,
          filename: file.name,
          status: "failed",
          error: String(e?.message || e),
        };
        upsertJobRow(fakeJob, "import");
      }
    }

    uploadFiles.value = "";
    ensurePolling();
  }

  window.addEventListener("popstate", () => {
    const next = normalizeDbPathFromUrl();
    void loadDirectory(next, { push: false, force: false });
  });

  selectAllBox.addEventListener("change", () => {
    toggleSelectAll(Boolean(selectAllBox.checked));
  });

  btnDeleteSelected.addEventListener("click", async () => {
    await deleteSelected(Array.from(selectedPaths.values()));
  });

  btnUpload.addEventListener("click", () => {
    uploadFiles.click();
  });

  uploadFiles.addEventListener("change", async () => {
    const files = Array.from(uploadFiles.files || []);
    await submitUploads(files);
  });

  btnRefresh.addEventListener("click", async () => {
    await refreshCurrentDirectory();
  });

  btnRefreshTree.addEventListener("click", async () => {
    await refreshCurrentDirectory();
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
      await refreshCurrentDirectory();
    } catch (e) {
      setStatus(`创建失败：${e?.message || e}`);
    }
  });

  btnRescan?.addEventListener("click", async () => {
    try {
      const job = await fetchJson(`/api/scan?path=${encodeURIComponent(currentPath)}`, { method: "POST" });
      activeScanJobId = String(job.job_id || "");
      if (activeScanJobId) {
        upsertJobRow(job, "scan");
        ensurePolling();
      }
    } catch (e) {
      setStatus(`触发重扫失败：${e?.message || e}`);
    }
  });

  await loadDirectory(currentPath, { push: false, force: true });
}
