import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Card } from "@/components/ui/Card";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { fetchJson } from "@/lib/api";
import type {
  CapabilitiesResponse,
  DbRowActionState,
  DocsTreeFile,
  DocsTreeResponse,
  ImportJob,
  JobStatus,
  MoveDocResponse,
  RenameDocResponse,
  ScanJob,
} from "@/lib/types";
import { buildDbUrl, dbPathFromUrl, normalizeDir } from "@/lib/urlState";
import { DbDirectoryTreePanel } from "@/pages/db/DbDirectoryTreePanel";
import { DbFileTable } from "@/pages/db/DbFileTable";
import { DbJobsPanel, type DisplayJob } from "@/pages/db/DbJobsPanel";
import { DbToolbarPanel } from "@/pages/db/DbToolbarPanel";

type BatchDeleteResult = {
  total: number;
  deleted: number;
  failed: number;
  results?: Array<{
    path?: string;
    ok?: boolean;
    error?: string;
    error_code?: string;
    details?: { candidates?: string[] };
  }>;
};

function toJobStatus(value: string | undefined): JobStatus {
  if (value === "success") return "success";
  if (value === "failed") return "failed";
  if (value === "running") return "running";
  return "queued";
}

function baseActionState(mode: DbRowActionState["mode"], value = ""): DbRowActionState {
  return {
    mode,
    value,
    error: "",
    phase: "idle",
  };
}

export function DbPage() {
  const [currentPath, setCurrentPath] = useState(() => dbPathFromUrl(window.location.search));
  const [treeCache, setTreeCache] = useState<Map<string, DocsTreeResponse>>(() => new Map());
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(() => new Set([""]));
  const [files, setFiles] = useState<DocsTreeFile[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => new Set());
  const [jobs, setJobs] = useState<DisplayJob[]>([]);
  const [status, setStatus] = useState("加载中...");
  const [actionResult, setActionResult] = useState("");
  const [actionError, setActionError] = useState(false);
  const [folderName, setFolderName] = useState("");
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse>({
    import_enabled: true,
    scan_enabled: true,
    import_reason: "",
    scan_reason: "",
  });
  const [rowActionStates, setRowActionStates] = useState<Record<string, DbRowActionState>>({});

  const activeImportJobIdsRef = useRef<Set<string>>(new Set());
  const activeScanJobIdRef = useRef("");
  const jobStatusByPathRef = useRef<Map<string, JobStatus>>(new Map());
  const pollTimerRef = useRef<number | null>(null);

  const selectAllChecked = useMemo(() => {
    if (files.length === 0) return false;
    return files.every((file) => selectedPaths.has(normalizeDir(file.relative_path || file.name || "")));
  }, [files, selectedPaths]);

  const selectedCount = selectedPaths.size;
  const importDisabledReason = capabilities.import_enabled
    ? ""
    : String(capabilities.import_reason || "导入服务不可用");
  const scanDisabledReason = capabilities.scan_enabled
    ? ""
    : String(capabilities.scan_reason || "重扫服务不可用");

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

  const getRowActionState = (path: string): DbRowActionState =>
    rowActionStates[path] || baseActionState("normal");

  const setRowActionState = (path: string, state: DbRowActionState) => {
    setRowActionStates((prev) => ({ ...prev, [path]: state }));
  };

  const clearRowActionState = (path: string) => {
    setRowActionStates((prev) => {
      const next = { ...prev };
      delete next[path];
      return next;
    });
  };

  const upsertJob = (job: ImportJob | ScanJob, kind: "import" | "scan") => {
    const statusValue = toJobStatus(job.status);
    const candidate = job as { relative_path?: string; filename?: string; path?: string };
    const pathText = String(candidate.relative_path || candidate.filename || candidate.path || "-");
    const errorText = String(job.error || "");
    const jobId = String(job.job_id || `${kind}-${Date.now()}`);

    if (kind === "import" && pathText && pathText !== "-") {
      jobStatusByPathRef.current.set(pathText, statusValue);
    }

    setJobs((prev) => {
      const rowId = `${kind}-${jobId}`;
      const next = prev.filter((item) => item.rowId !== rowId);
      next.unshift({
        rowId,
        kind,
        status: statusValue,
        pathText,
        error: errorText,
        updatedAt: Date.now(),
      });
      return next.slice(0, 80);
    });
  };

  const ensureTreeNode = async (path: string, force = false): Promise<DocsTreeResponse> => {
    const key = normalizeDir(path || "");
    if (!force && treeCache.has(key)) {
      return treeCache.get(key)!;
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
      return next;
    });

    return node;
  };

  const preloadPathChain = async (path: string, force = false) => {
    const target = normalizeDir(path || "");
    await ensureTreeNode("", force);
    if (!target) return;

    let acc = "";
    for (const segment of target.split("/")) {
      acc = acc ? `${acc}/${segment}` : segment;
      await ensureTreeNode(acc, force);
    }
  };

  const renderActionResult = (text: string, isError = false) => {
    setActionResult(text);
    setActionError(isError);
  };

  const loadCapabilities = async () => {
    try {
      const payload = await fetchJson<CapabilitiesResponse>("/api/capabilities");
      setCapabilities({
        import_enabled: Boolean(payload.import_enabled),
        scan_enabled: Boolean(payload.scan_enabled),
        import_reason: String(payload.import_reason || ""),
        scan_reason: String(payload.scan_reason || ""),
      });
    } catch (error) {
      const message = String((error as Error)?.message || error);
      renderActionResult(`加载能力信息失败：${message}`, true);
    }
  };

  const pruneSelection = (visibleFiles: DocsTreeFile[]) => {
    const visible = new Set(visibleFiles.map((file) => normalizeDir(file.relative_path || file.name || "")));
    setSelectedPaths((prev) => {
      const next = new Set<string>();
      for (const path of prev) {
        if (visible.has(path)) next.add(path);
      }
      return next;
    });
    setRowActionStates((prev) => {
      const next: Record<string, DbRowActionState> = {};
      for (const [path, state] of Object.entries(prev)) {
        if (visible.has(path)) next[path] = state;
      }
      return next;
    });
  };

  const loadDirectory = async (path: string, options?: { push?: boolean; force?: boolean }) => {
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
  };

  const refreshCurrentDirectory = async () => {
    await loadDirectory(currentPath, { force: true, push: false });
  };

  const stopPolling = () => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const ensurePolling = () => {
    if (pollTimerRef.current !== null) return;

    pollTimerRef.current = window.setInterval(async () => {
      const doneImport: string[] = [];

      for (const jobId of activeImportJobIdsRef.current.values()) {
        try {
          const job = await fetchJson<ImportJob>(`/api/import/${encodeURIComponent(jobId)}`);
          upsertJob(job, "import");
          if (["success", "failed"].includes(String(job.status || ""))) {
            doneImport.push(jobId);
          }
        } catch {
          doneImport.push(jobId);
        }
      }

      doneImport.forEach((jobId) => activeImportJobIdsRef.current.delete(jobId));

      if (activeScanJobIdRef.current) {
        try {
          const scanJob = await fetchJson<ScanJob>(`/api/scan/${encodeURIComponent(activeScanJobIdRef.current)}`);
          upsertJob(scanJob, "scan");
          if (["success", "failed"].includes(String(scanJob.status || ""))) {
            activeScanJobIdRef.current = "";
          }
        } catch {
          activeScanJobIdRef.current = "";
        }
      }

      if (activeImportJobIdsRef.current.size === 0 && !activeScanJobIdRef.current) {
        stopPolling();
        await refreshCurrentDirectory();
      }
    }, 1500);
  };

  const formatFailedSummary = (payload: BatchDeleteResult): string => {
    const failed = (payload.results || []).filter((item) => !item.ok);
    if (failed.length === 0) return "";

    return failed
      .slice(0, 3)
      .map((item) => {
        const path = String(item.path || "-");
        const code = String(item.error_code || "").toUpperCase();
        if (code === "CONFLICT") {
          const candidates = Array.isArray(item.details?.candidates)
            ? item.details!.candidates!.slice(0, 3).join(", ")
            : "";
          return candidates ? `${path}: 命名冲突，请使用完整相对路径，候选: ${candidates}` : `${path}: 命名冲突，请使用完整相对路径`;
        }
        return `${path}: ${String(item.error || "unknown error")}`;
      })
      .join(" | ");
  };

  const deleteSelected = async (paths: string[]) => {
    if (!capabilities.import_enabled) {
      const message = importDisabledReason || "导入服务不可用";
      renderActionResult(`删除不可用：${message}`, true);
      setStatus(`删除不可用：${message}`);
      return;
    }

    const list = paths.map((path) => normalizeDir(path || "")).filter(Boolean);
    if (list.length === 0) return;

    const sample = list.slice(0, 5).join("\n");
    const tail = list.length > 5 ? "\n..." : "";
    const ok = window.confirm(
      `确认删除 ${list.length} 个文件？\n将删除数据库记录和磁盘文件。\n\n示例路径：\n${sample}${tail}`
    );
    if (!ok) return;

    renderActionResult("");
    setStatus(`正在删除 ${list.length} 个文件...`);

    try {
      const payload = await fetchJson<BatchDeleteResult>("/api/docs/batch-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paths: list }),
      });

      const summary = formatFailedSummary(payload);
      renderActionResult(
        summary
          ? `删除完成：成功 ${payload.deleted}/${payload.total}，失败 ${payload.failed}（${summary}）`
          : `删除完成：成功 ${payload.deleted}/${payload.total}，失败 ${payload.failed}`
      );
      setSelectedPaths(new Set());
      await refreshCurrentDirectory();
    } catch (error) {
      const message = String((error as Error)?.message || error);
      renderActionResult(`删除失败：${message}`, true);
      setStatus(`删除失败：${message}`);
    }
  };

  const submitUploads = async (uploadFiles: File[]) => {
    if (!capabilities.import_enabled) {
      const message = importDisabledReason || "导入服务不可用";
      renderActionResult(`上传不可用：${message}`, true);
      setStatus(`上传不可用：${message}`);
      return;
    }

    if (uploadFiles.length === 0) {
      setStatus("请选择 PDF 文件");
      return;
    }

    setStatus(`准备上传 ${uploadFiles.length} 个文件...`);
    renderActionResult("");

    for (const file of uploadFiles) {
      try {
        const response = await fetch(
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

        const data = (await response.json().catch(() => ({}))) as ImportJob & { message?: string };
        if (!response.ok) throw new Error(String(data.message || `${response.status} ${response.statusText}`));

        activeImportJobIdsRef.current.add(String(data.job_id));
        upsertJob(data, "import");
      } catch (error) {
        upsertJob(
          {
            job_id: `error-${Date.now()}`,
            filename: file.name,
            status: "failed",
            error: String((error as Error)?.message || error),
          },
          "import"
        );
      }
    }

    ensurePolling();
  };

  const createFolder = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!capabilities.import_enabled) {
      const message = importDisabledReason || "导入服务不可用";
      renderActionResult(`创建目录不可用：${message}`, true);
      setStatus(`创建目录不可用：${message}`);
      return;
    }

    const name = folderName.trim();
    if (!name) return;

    try {
      await fetchJson("/api/folders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: currentPath, name }),
      });
      setFolderName("");
      await refreshCurrentDirectory();
    } catch (error) {
      setStatus(`创建失败：${String((error as Error)?.message || error)}`);
    }
  };

  const triggerRescan = async () => {
    if (!capabilities.scan_enabled) {
      const message = scanDisabledReason || "重扫服务不可用";
      renderActionResult(`重扫不可用：${message}`, true);
      setStatus(`重扫不可用：${message}`);
      return;
    }

    try {
      const job = await fetchJson<ScanJob>(`/api/scan?path=${encodeURIComponent(currentPath)}`, { method: "POST" });
      activeScanJobIdRef.current = String(job.job_id || "");
      if (activeScanJobIdRef.current) {
        upsertJob(job, "scan");
        ensurePolling();
      }
    } catch (error) {
      setStatus(`触发重扫失败：${String((error as Error)?.message || error)}`);
    }
  };

  useEffect(() => {
    const onPopState = () => {
      void loadDirectory(dbPathFromUrl(window.location.search), { push: false, force: false });
    };

    window.addEventListener("popstate", onPopState);
    void loadCapabilities();
    void loadDirectory(currentPath, { push: false, force: true });

    return () => {
      window.removeEventListener("popstate", onPopState);
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleSelect = (path: string) => {
    const normalized = normalizeDir(path || "");
    if (!normalized) return;
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(normalized)) next.delete(normalized);
      else next.add(normalized);
      return next;
    });
  };

  const toggleSelectAll = (checked: boolean) => {
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
  };

  const beginRename = (path: string) => {
    const filename = path.split("/").pop() || path;
    setRowActionState(path, baseActionState("renaming", filename));
  };

  const beginMove = (path: string) => {
    setRowActionState(path, baseActionState("moving", currentPath));
  };

  const applyRename = async (path: string) => {
    if (!capabilities.import_enabled) {
      const message = importDisabledReason || "导入服务不可用";
      setRowActionState(path, { ...baseActionState("renaming"), error: message, phase: "error" });
      return;
    }
    const state = getRowActionState(path);
    const newName = state.value.trim();
    if (!newName) {
      setRowActionState(path, { ...state, error: "请输入新文件名", phase: "error" });
      return;
    }

    setRowActionState(path, { ...state, error: "", phase: "pending" });
    try {
      const result = await fetchJson<RenameDocResponse>("/api/docs/rename", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, new_name: newName }),
      });
      setRowActionState(path, { ...state, phase: "success" });
      clearRowActionState(path);
      renderActionResult(`改名成功：${result.old_path} -> ${result.new_path}`);
      await refreshCurrentDirectory();
    } catch (error) {
      const message = String((error as Error)?.message || error);
      setRowActionState(path, { ...state, error: message, phase: "error" });
    }
  };

  const applyMove = async (path: string) => {
    if (!capabilities.import_enabled) {
      const message = importDisabledReason || "导入服务不可用";
      setRowActionState(path, { ...baseActionState("moving"), error: message, phase: "error" });
      return;
    }

    const state = getRowActionState(path);
    const targetDir = normalizeDir(state.value || "");
    setRowActionState(path, { ...state, error: "", phase: "pending" });

    try {
      const result = await fetchJson<MoveDocResponse>("/api/docs/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, target_dir: targetDir }),
      });
      setRowActionState(path, { ...state, phase: "success" });
      clearRowActionState(path);
      renderActionResult(`移动成功：${result.old_path} -> ${result.new_path}`);
      await refreshCurrentDirectory();
    } catch (error) {
      const message = String((error as Error)?.message || error);
      setRowActionState(path, { ...state, error: message, phase: "error" });
    }
  };

  const breadcrumbParts = currentPath ? currentPath.split("/") : [];

  return (
    <AppShell actions={[{ href: "/search", label: "搜索", icon: <MaterialSymbol name="search" size={18} /> }]}>
      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <DbDirectoryTreePanel
          currentPath={currentPath}
          treeCache={treeCache}
          expandedDirs={expandedDirs}
          onRefresh={() => void refreshCurrentDirectory()}
          onLoadDirectory={(path) => void loadDirectory(path, { push: true, force: false })}
          onToggleExpand={(path, expanded) => {
            setExpandedDirs((prev) => {
              const next = new Set(prev);
              if (expanded) next.add(path);
              else next.delete(path);
              return next;
            });
          }}
          onEnsureTreeNode={async (path) => {
            await ensureTreeNode(path);
          }}
        />

        <div className="grid min-w-0 gap-3">
          <Card className="grid min-w-0 gap-3">
            <DbToolbarPanel
              breadcrumbParts={breadcrumbParts}
              status={status}
              selectedCount={selectedCount}
              folderName={folderName}
              onFolderNameChange={setFolderName}
              capabilities={capabilities}
              importDisabledReason={importDisabledReason}
              scanDisabledReason={scanDisabledReason}
              actionResult={actionResult}
              actionError={actionError}
              onNavigate={(path) => void loadDirectory(path, { push: true, force: false })}
              onUploadFiles={(selected) => void submitUploads(selected)}
              onDeleteSelected={() => void deleteSelected(Array.from(selectedPaths))}
              onTriggerRescan={() => void triggerRescan()}
              onRefresh={() => void refreshCurrentDirectory()}
              onCreateFolder={() => void createFolder()}
            />

            <DbFileTable
              files={files}
              selectedPaths={selectedPaths}
              selectAllChecked={selectAllChecked}
              knownDirectories={knownDirectories}
              jobStatusByPath={jobStatusByPathRef.current}
              capabilitiesImportEnabled={capabilities.import_enabled}
              importDisabledReason={importDisabledReason}
              getRowActionState={getRowActionState}
              onSetRowActionState={setRowActionState}
              onClearRowActionState={clearRowActionState}
              onToggleSelect={toggleSelect}
              onToggleSelectAll={toggleSelectAll}
              onBeginRename={beginRename}
              onBeginMove={beginMove}
              onApplyRename={(path) => void applyRename(path)}
              onApplyMove={(path) => void applyMove(path)}
              onDeleteSingle={(path) => void deleteSelected([path])}
            />
          </Card>

          <DbJobsPanel jobs={jobs} />
        </div>
      </div>
    </AppShell>
  );
}
