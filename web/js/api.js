/**
 * API模块
 * 提供与后端API交互的函数
 */

/**
 * 获取JSON数据
 */
export async function fetchJson(url) {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return await res.json();
}

/**
 * 搜索零件
 */
export async function searchParts(params) {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.match) query.set("match", params.match);
  if (params.page) query.set("page", params.page);
  if (params.page_size) query.set("page_size", params.page_size);
  if (params.include_notes) query.set("include_notes", "1");

  return fetchJson(`/api/search?${query.toString()}`);
}

/**
 * 获取零件详情
 */
export async function getPartDetail(partId) {
  return fetchJson(`/api/part/${partId}`);
}

/**
 * 获取文档列表
 */
export async function getDocuments() {
  return fetchJson("/api/docs");
}

/**
 * 获取PDF渲染URL
 */
export function getRenderUrl(pdfName, page, scale = 2) {
  return `/render/${encodeURIComponent(pdfName)}/${page}.png`;
}

/**
 * 获取PDF文件URL
 */
export function getPdfUrl(pdfName) {
  return `/pdf/${encodeURIComponent(pdfName)}`;
}

/**
 * 健康检查
 */
export async function healthCheck() {
  return fetchJson("/api/health");
}
