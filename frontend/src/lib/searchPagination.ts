export function resolvePageSize(value: unknown, fallbackPageSize: number): number {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  if (Number.isFinite(parsed) && parsed > 0) {
    return parsed;
  }
  return Math.max(1, fallbackPageSize);
}

export function computeTotalPages(total: number, pageSize: number): number {
  const safeTotal = Math.max(0, Number(total) || 0);
  const safeSize = Math.max(1, Number(pageSize) || 1);
  return Math.max(1, Math.ceil(safeTotal / safeSize));
}

export function clampPage(page: number, totalPages: number): number {
  const safePage = Math.max(1, Number(page) || 1);
  const safeTotalPages = Math.max(1, Number(totalPages) || 1);
  return Math.min(safePage, safeTotalPages);
}

export function shouldRefetchForClampedPage(requestedPage: number, clampedPage: number, total: number): boolean {
  return Math.max(0, Number(total) || 0) > 0 && requestedPage !== clampedPage;
}
