import { useCallback, useMemo, useRef, useState } from "react";
import { fetchJson } from "@/lib/api";
import type { DocsTreeDirectory, DocsTreeFile, DocsTreeResponse } from "@/lib/types";
import { buildDbUrl, normalizeDir } from "@/lib/urlState";

type LoadDirectoryOptions = {
  push?: boolean;
  force?: boolean;
};

type UseDbDirectoryModelParams = {
  initialPath: string;
};

function toTopLevelPath(path: string): string {
  const normalized = normalizeDir(path || "");
  if (!normalized) return "";
  return normalized.split("/")[0] || "";
}

export function useDbDirectoryModel({ initialPath }: UseDbDirectoryModelParams) {
  const [currentPath, setCurrentPath] = useState(() => toTopLevelPath(initialPath || ""));
  const [treeCache, setTreeCache] = useState<Map<string, DocsTreeResponse>>(() => new Map());
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(() => new Set([""]));
  const [directories, setDirectories] = useState<DocsTreeDirectory[]>([]);
  const [files, setFiles] = useState<DocsTreeFile[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => new Set());
  const [status, setStatus] = useState("");
  const treeCacheRef = useRef(treeCache);

  const knownDirectories = useMemo(() => {
    const out = new Set<string>([""]);
    const rootNode = treeCache.get("");
    for (const dir of rootNode?.directories || []) {
      out.add(toTopLevelPath(dir.path || ""));
    }
    return Array.from(out.values()).sort((a, b) => a.localeCompare(b));
  }, [treeCache]);

  const selectedCount = selectedPaths.size;
  const breadcrumbParts = currentPath ? currentPath.split("/") : [];

  const ensureTreeNode = useCallback(async (path: string, force = false): Promise<DocsTreeResponse> => {
    const key = toTopLevelPath(path || "");
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
      const target = toTopLevelPath(path || "");
      await ensureTreeNode("", force);
      if (!target) return;
      await ensureTreeNode(target, force);
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
      const target = toTopLevelPath(path || "");
      setStatus("加载中...");

      try {
        await preloadPathChain(target, force);
        const payload = await ensureTreeNode(target, force);
        const resolvedPath = toTopLevelPath(payload.path || target);
        setCurrentPath(resolvedPath);
        setDirectories(resolvedPath ? [] : (payload.directories || []));
        setFiles(payload.files || []);
        pruneSelection(payload.files || []);

        setExpandedDirs((prev) => {
          const next = new Set(prev);
          next.add("");
          if (resolvedPath) {
            next.add(resolvedPath);
          }
          return next;
        });

        if (push) history.pushState({}, "", buildDbUrl(resolvedPath));
        setStatus("");
      } catch (error) {
        setStatus(`加载失败：${String((error as Error)?.message || error)}`);
        setDirectories([]);
        setFiles([]);
      }
    },
    [ensureTreeNode, preloadPathChain, pruneSelection]
  );

  const refreshCurrentDirectory = useCallback(async () => {
    await loadDirectory(currentPath, { force: true, push: false });
  }, [currentPath, loadDirectory]);

  const setSelection = useCallback((paths: string[]) => {
    const next = new Set<string>();
    for (const raw of paths) {
      const normalized = normalizeDir(raw || "");
      if (normalized) next.add(normalized);
    }
    setSelectedPaths(next);
  }, []);

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
    directories,
    files,
    selectedPaths,
    status,
    knownDirectories,
    selectedCount,
    breadcrumbParts,
    setStatus,
    setSelection,
    loadDirectory,
    refreshCurrentDirectory,
    ensureTreeNode,
    toggleExpandDir,
    clearSelection,
  };
}
