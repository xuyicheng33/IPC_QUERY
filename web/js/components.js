/**
 * UI组件模块
 * 提供可复用的UI组件
 */

import {
  $,
  escapeHtml,
  highlightHtml,
  fmtFig,
  fmtPn,
  fmtSrc,
  fmtUnits,
  labelRowKind,
  labelPnMethod,
  badge,
} from "./utils.js";

/**
 * 结果卡片组件
 */
export function createResultCard(result, queryTokens, isActive) {
  const card = document.createElement("div");
  card.className = `card${isActive ? " active" : ""}`;
  card.dataset.id = result.id;

  const pn = fmtPn(result);
  const nom = result.nomenclature_preview || "";
  const src = fmtSrc(result);

  card.innerHTML = `
    <div class="cardPn">${highlightHtml(pn, queryTokens)}</div>
    <div class="cardNom">${highlightHtml(nom, queryTokens)}</div>
    <div class="cardSrc">${escapeHtml(src)}</div>
  `;

  return card;
}

/**
 * 详情面板组件
 */
export function renderDetailPanel(detail, state) {
  const part = detail.part;
  const hierarchy = detail.hierarchy || {};

  let html = `
    <div class="detailTop">
      <div class="detailPn">${escapeHtml(fmtPn(part))}</div>
      <div class="detailSrc">${escapeHtml(fmtSrc(part))}</div>
    </div>
  `;

  // 信息网格
  html += '<div class="grid2">';
  if (part.figure_code) {
    html += `
      <div class="kv">
        <div class="kvLabel">图号</div>
        <div class="kvVal">${escapeHtml(part.figure_code)}</div>
      </div>
    `;
  }
  if (part.fig_item) {
    html += `
      <div class="kv">
        <div class="kvLabel">ITEM</div>
        <div class="kvVal">${escapeHtml(part.fig_item)}</div>
      </div>
    `;
  }
  if (part.effectivity) {
    html += `
      <div class="kv">
        <div class="kvLabel">有效性</div>
        <div class="kvVal">${escapeHtml(part.effectivity)}</div>
      </div>
    `;
  }
  if (part.units_per_assy) {
    html += `
      <div class="kv">
        <div class="kvLabel">单位</div>
        <div class="kvVal">${escapeHtml(fmtUnits(part.units_per_assy))}</div>
      </div>
    `;
  }
  html += "</div>";

  // 术语描述
  if (part.nomenclature_full || part.nomenclature) {
    const nom = part.nomenclature_full || part.nomenclature;
    html += `
      <div class="block">
        <div class="blockLabel">术语描述</div>
        <div class="blockContent">${escapeHtml(nom).replace(/\n/g, "<br>")}</div>
      </div>
    `;
  }

  // 层级导航
  if (hierarchy.ancestors?.length || hierarchy.siblings?.length || hierarchy.children?.length) {
    html += '<div class="block"><div class="blockLabel">层级关系</div><div class="hierGrid">';

    // 父辈
    if (hierarchy.ancestors?.length) {
      html += '<div class="hierCol"><div class="hierLabel">父辈</div>';
      for (const anc of hierarchy.ancestors) {
        html += `<div class="hierBtn" data-id="${anc.id}">${escapeHtml(fmtPn(anc))}</div>`;
      }
      html += "</div>";
    }

    // 同级
    if (hierarchy.siblings?.length) {
      html += '<div class="hierCol"><div class="hierLabel">同级</div>';
      for (const sib of hierarchy.siblings.slice(0, 10)) {
        html += `<div class="hierBtn" data-id="${sib.id}">${escapeHtml(fmtPn(sib))}</div>`;
      }
      html += "</div>";
    }

    // 子级
    if (hierarchy.children?.length) {
      html += '<div class="hierCol"><div class="hierLabel">子级</div>';
      for (const child of hierarchy.children.slice(0, 10)) {
        html += `<div class="hierBtn" data-id="${child.id}">${escapeHtml(fmtPn(child))}</div>`;
      }
      html += "</div>";
    }

    html += "</div></div>";
  }

  // 预览区域
  if (part.source_pdf && part.page_num) {
    html += `
      <div class="block">
        <div class="blockLabel">页面预览</div>
        <div class="previewArea">
          <img src="/render/${encodeURIComponent(part.source_pdf)}/${part.page_num}.png"
               alt="Page ${part.page_num}"
               class="previewImg"
               loading="lazy">
        </div>
      </div>
    `;
  }

  return html;
}

/**
 * 分页组件
 */
export function renderPagination(currentPage, totalResults, pageSize) {
  const totalPages = Math.ceil(totalResults / pageSize);
  if (totalPages <= 1) return "";

  let html = '<div class="pager">';

  // 上一页
  if (currentPage > 1) {
    html += `<button class="btn ghost" data-page="${currentPage - 1}">上一页</button>`;
  }

  // 页码
  const start = Math.max(1, currentPage - 2);
  const end = Math.min(totalPages, currentPage + 2);

  if (start > 1) {
    html += `<button class="btn ghost" data-page="1">1</button>`;
    if (start > 2) html += '<span class="pagerEllipsis">...</span>';
  }

  for (let p = start; p <= end; p++) {
    const cls = p === currentPage ? "btn primary" : "btn ghost";
    html += `<button class="${cls}" data-page="${p}">${p}</button>`;
  }

  if (end < totalPages) {
    if (end < totalPages - 1) html += '<span class="pagerEllipsis">...</span>';
    html += `<button class="btn ghost" data-page="${totalPages}">${totalPages}</button>`;
  }

  // 下一页
  if (currentPage < totalPages) {
    html += `<button class="btn ghost" data-page="${currentPage + 1}">下一页</button>`;
  }

  html += "</div>";
  return html;
}

/**
 * Toast通知组件
 */
export function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  const container = $(".toastContainer") || document.body;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("fade-out");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

/**
 * 加载骨架屏
 */
export function showSkeleton(container, count = 5) {
  let html = "";
  for (let i = 0; i < count; i++) {
    html += `
      <div class="skeleton">
        <div class="skeleton-line skeleton-pn"></div>
        <div class="skeleton-line skeleton-nom"></div>
        <div class="skeleton-line skeleton-src"></div>
      </div>
    `;
  }
  container.innerHTML = html;
}

/**
 * 空状态组件
 */
export function showEmptyState(container, message = "暂无结果") {
  container.innerHTML = `<div class="emptyState">${escapeHtml(message)}</div>`;
}

/**
 * 错误状态组件
 */
export function showErrorState(container, message = "加载失败") {
  container.innerHTML = `<div class="errorState">${escapeHtml(message)}</div>`;
}
