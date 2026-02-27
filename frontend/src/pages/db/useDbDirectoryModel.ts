import { useCallback, useMemo, useRef, useState } from "react";
import { fetchJson } from "@/lib/api";
import type { DocsTreeFile, DocsTreeResponse } from "@/lib/types";
import { buildDbUrl, normalizeDir } from "@/lib/urlState";

type LoadDirectoryOptions = {
  push?: boolean;
  force?: boolean;
};

type UseDbDirectoryModelParams = {
  initialPath: string;
};

export function useDbDirectoryModel({ initialPath }: UseDbDirectoryModelParams) {
  const [currentPath, setCurrentPath] = useState(() => normalizeDir(initialPath || ""));
  const [treeCache, setTreeCache] = useState<Map<string, DocsTreeResponse>>(() => new Map());
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(() => new Set([""]));
  const [files, setFiles] = useState<DocsTreeFile[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => new Set());
  const [status, setStatus] = useState("加载中...");
  const treeCacheRef = useRef(treeCache);

  const selectAllChecked = useMemo(() => {
    if (files.length === 0) return false;
    return files.every((file) => selectedPaths.has(normalizeDir(file.relative_path || file.name || "")));
  }, [files, selectedPaths]);

  const knownDirectories = useMemo(() => {
    const out = new Set<string>([""]);
    for (const [key, node] of treeCache.entries()) {
      out.add(normalizeDir(key || ""));
      for (const dir of node.directories || []) {
        out.add(normalizeDir(dir.path || ""));
      }
    }
    return Array.from(out.values()).sort((a, b) => a.localeCompare(b));
  }, [treeCache]);

  const selectedCount = selectedPaths.size;
  const breadcrumbParts = currentPath ? currentPath.split("/") : [];

  const ensureTreeNode = useCallback(async (path: string, force = false): Promise<DocsTreeResponse> => {
    const key = normalizeDir(path || "");
    const cached = treeCacheRef.current.get(key);
    if (!force && cached) {
      return cached;
    }

    const payload = await fetchJson<DocsTreeResponse>(`/api/docs/tree?path=${encodeURIComponent(key)}`);
    const node: DocsTreeResponse = {
      path: normalizeDir(payload.path || key),
      directories: Array.isArray(payload.directories) ? payload.directories : [],
      files: Array.isArray(payload.files) ? payload.files : [],
    };

    setTreeCache((prev) => {
      const next = new Map(prev);
      next.set(node.path, node);
      if (node.path !== key) next.set(key, node);
      treeCacheRef.current = next;
      return next;
    });

    return node;
  }, []);

  const preloadPathChain = useCallback(
    async (path: string, force = false) => {
      const target = normalizeDir(path || "");
      await ensureTreeNode("", force);
      if (!target) return;

      let acc = "";
      for (const segment of target.split("/")) {
        acc = acc ? `${acc}/${segment}` : segment;
        await ensureTreeNode(acc, force);
      }
    },
    [ensureTreeNode]
  );

  const pruneSelection = useCallback((visibleFiles: DocsTreeFile[]) => {
    const visible = new Set(visibleFiles.map((file) => normalizeDir(file.relative_path || file.name || "")));
    setSelectedPaths((prev) => {
      const next = new Set<string>();
      for (const path of prev) {
        if (visible.has(path)) next.add(path);
      }
      return next;
    });
  }, []);

  const loadDirectory = useCallback(
    async (path: string, options?: LoadDirectoryOptions) => {
      const push = Boolean(options?.push);
      const force = Boolean(options?.force);
      const target = normalizeDir(path || "");
      setStatus("加载中...");

      try {
        await preloadPathChain(target, force);
        const payload = await ensureTreeNode(target, force);
        const resolvedPath = normalizeDir(payload.path || target);
        setCurrentPath(resolvedPath);
        setFiles(payload.files || []);
        pruneSelection(payload.files || []);

        setExpandedDirs((prev) => {
          const next = new Set(prev);
          next.add("");
          if (resolvedPath) {
            let acc = "";
            for (const segment of resolvedPath.split("/")) {
              acc = acc ? `${acc}/${segment}` : segment;
              next.add(acc);
            }
          }
          return next;
        });

        if (push) history.pushState({}, "", buildDbUrl(resolvedPath));
        setStatus(`目录 ${resolvedPath || "/"} · 文件 ${(payload.files || []).length}`);
      } catch (error) {
        setStatus(`加载失败：${String((error as Error)?.message || error)}`);
        setFiles([]);
      }
    },
    [ensureTreeNode, preloadPathChain, pruneSelection]
  );

  const refreshCurrentDirectory = useCallback(async () => {
    await loadDirectory(currentPath, { force: true, push: false });
  }, [currentPath, loadDirectory]);

  const toggleSelect = useCallback((path: string) => {
    const normalized = normalizeDir(path || "");
    if (!normalized) return;
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(normalized)) next.delete(normalized);
      else next.add(normalized);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(
    (checked: boolean) => {
      if (!checked) {
        setSelectedPaths(new Set());
        return;
      }
      const next = new Set<string>();
      files.forEach((file) => {
        const normalized = normalizeDir(file.relative_path || file.name || "");
        if (normalized) next.add(normalized);
      });
      setSelectedPaths(next);
    },
    [files]
  );

  const clearSelection = useCallback(() => {
    setSelectedPaths(new Set());
  }, []);

  const toggleExpandDir = useCallback((path: string, expanded: boolean) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (expanded) next.add(path);
      else next.delete(path);
      return next;
    });
  }, []);

  return {
    currentPath,
    treeCache,
    expandedDirs,
    files,
    selectedPaths,
    status,
    selectAllChecked,
    knownDirectories,
    selectedCount,
    breadcrumbParts,
    setStatus,
    loadDirectory,
    refreshCurrentDirectory,
    ensureTreeNode,
    toggleExpandDir,
    toggleSelect,
    toggleSelectAll,
    clearSelection,
  };
}
