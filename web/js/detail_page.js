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
  const keywordUtils = getKeywordUtils();

  try {
    const data = await fetchJson(`/api/part/${id}`);
    const p = data?.part || {};
    const pn = (p.pn || p.part_number_canonical || p.part_number_cell || "-").toString();
    const sourceRelativePath = (p.source_relative_path || p.source_pdf || "").toString();
    const pdf = (sourceRelativePath || p.pdf || "").toString();
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
    const descRaw = (p.nom || p.nomenclature || p.nomenclature_clean || "").toString();
    const descText = descRaw.trim();
    const descEl = $("#partDesc");
    const optionalFlagEl = $("#optionalFlag");
    const replaceFlagEl = $("#replaceFlag");
    const flags = keywordUtils.detectKeywordFlags(descText);

    if (optionalFlagEl) {
      optionalFlagEl.textContent = flags.optional ? "是" : "否";
      optionalFlagEl.classList.toggle("yes", Boolean(flags.optional));
    }
    if (replaceFlagEl) {
      replaceFlagEl.textContent = flags.replace ? "是" : "否";
      replaceFlagEl.classList.toggle("yes", Boolean(flags.replace));
    }

    if (descEl) {
      if (!descText) {
        descEl.textContent = "—";
      } else {
        descEl.innerHTML = keywordUtils.highlightKeywords(descText, escapeHtml);
      }
    }

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
    const descEl = $("#partDesc");
    if (descEl) descEl.textContent = `加载失败：${e?.message || e}`;
    const optionalFlagEl = $("#optionalFlag");
    const replaceFlagEl = $("#replaceFlag");
    if (optionalFlagEl) optionalFlagEl.textContent = "否";
    if (replaceFlagEl) replaceFlagEl.textContent = "否";
  }
}
