import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Folder,
  FolderPlus,
  LoaderCircle,
  RefreshCw,
  ScanSearch,
  Trash2,
  Upload,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Table, TableWrap, TD, TH } from "@/components/ui/Table";
import { fetchJson } from "@/lib/api";
import type { DocsTreeFile, DocsTreeResponse, ImportJob, JobStatus, ScanJob } from "@/lib/types";
import { buildDbUrl, dbPathFromUrl, normalizeDir } from "@/lib/urlState";

type DisplayJob = {
  rowId: string;
  kind: "import" | "scan";
  status: JobStatus;
  pathText: string;
  error: string;
  updatedAt: number;
};

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

  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const activeImportJobIdsRef = useRef<Set<string>>(new Set());
  const activeScanJobIdRef = useRef("");
  const jobStatusByPathRef = useRef<Map<string, JobStatus>>(new Map());
  const pollTimerRef = useRef<number | null>(null);

  const selectAllChecked = useMemo(() => {
    if (files.length === 0) return false;
    return files.every((file) => selectedPaths.has(normalizeDir(file.relative_path || file.name || "")));
  }, [files, selectedPaths]);

  const selectedCount = selectedPaths.size;

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

  const pruneSelection = (visibleFiles: DocsTreeFile[]) => {
    const visible = new Set(visibleFiles.map((file) => normalizeDir(file.relative_path || file.name || "")));
    setSelectedPaths((prev) => {
      const next = new Set<string>();
      for (const path of prev) {
        if (visible.has(path)) next.add(path);
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

    if (uploadInputRef.current) uploadInputRef.current.value = "";
    ensurePolling();
  };

  const createFolder = async (event: FormEvent) => {
    event.preventDefault();
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

  const renderTree = (path: string, depth: number): React.ReactNode => {
    const node = treeCache.get(path);
    if (!node) return null;

    const entries: React.ReactNode[] = [];

    for (const dir of node.directories || []) {
      const dirPath = normalizeDir(dir.path || "");
      const expanded = expandedDirs.has(dirPath);
      entries.push(
        <div key={`dir-${dirPath}`} className="flex flex-col">
          <div
            className={`flex items-center gap-1 rounded-md px-1 py-0.5 ${dirPath === currentPath ? "bg-accent-soft" : "hover:bg-surface-soft"}`}
            style={{ paddingLeft: `${depth * 14}px` }}
          >
            <button
              type="button"
              className="inline-flex h-6 w-6 items-center justify-center rounded border border-border bg-surface hover:bg-surface-soft"
              onClick={() => {
                if (expanded) {
                  setExpandedDirs((prev) => {
                    const next = new Set(prev);
                    next.delete(dirPath);
                    return next;
                  });
                  return;
                }

                setExpandedDirs((prev) => {
                  const next = new Set(prev);
                  next.add(dirPath);
                  return next;
                });
                void ensureTreeNode(dirPath);
              }}
              aria-label={expanded ? "收起目录" : "展开目录"}
            >
              {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            </button>
            <button
              type="button"
              className="flex flex-1 items-center gap-1.5 rounded px-1 py-1 text-left font-mono text-xs hover:bg-surface"
              onClick={() => {
                void loadDirectory(dirPath, { push: true, force: false });
              }}
            >
              <Folder className="h-3.5 w-3.5 text-muted" />
              {dir.name || dirPath || "-"}
            </button>
          </div>
          {expanded ? (
            <>
              {(treeCache.get(dirPath)?.files || []).map((file) => (
                <div
                  key={`file-${file.relative_path}`}
                  className="flex items-center gap-1.5 py-1 text-xs text-muted"
                  style={{ paddingLeft: `${(depth + 1) * 14}px` }}
                >
                  <FileText className="h-3.5 w-3.5" />
                  <span className="font-mono">{file.relative_path || file.name || "-"}</span>
                </div>
              ))}
              {renderTree(dirPath, depth + 1)}
            </>
          ) : null}
        </div>
      );
    }

    return entries;
  };

  const breadcrumbParts = currentPath ? currentPath.split("/") : [];

  return (
    <AppShell actions={[{ href: "/search", label: "搜索" }]}>
      <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Card className="grid gap-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium">目录树</div>
            <Button variant="ghost" className="h-9 gap-2 px-3" onClick={() => void refreshCurrentDirectory()}>
              <RefreshCw className="h-4 w-4" />
              刷新树
            </Button>
          </div>

          <div className="min-h-[500px] rounded-md border border-border bg-surface p-2">
            <div className={`mb-1 flex items-center rounded-md px-1 py-1 ${currentPath === "" ? "bg-accent-soft" : ""}`}>
              <button
                type="button"
                className="flex flex-1 items-center gap-1.5 rounded px-1 py-1 text-left font-mono text-xs hover:bg-surface-soft"
                onClick={() => {
                  void loadDirectory("", { push: true, force: false });
                }}
              >
                <Folder className="h-3.5 w-3.5 text-muted" />/
              </button>
            </div>

            {(treeCache.get("")?.files || []).map((file) => (
              <div key={`root-file-${file.relative_path}`} className="flex items-center gap-1.5 py-1 pl-4 text-xs text-muted">
                <FileText className="h-3.5 w-3.5" />
                <span className="font-mono">{file.relative_path || file.name || "-"}</span>
              </div>
            ))}

            {renderTree("", 1)}
          </div>
        </Card>

        <Card className="grid gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="font-mono text-xs">
              <a
                href="/db"
                onClick={(event) => {
                  event.preventDefault();
                  void loadDirectory("", { push: true, force: false });
                }}
                className="text-accent"
              >
                /
              </a>
              {breadcrumbParts.map((part, index) => {
                const path = breadcrumbParts.slice(0, index + 1).join("/");
                return (
                  <span key={path}>
                    /{" "}
                    <a
                      href={buildDbUrl(path)}
                      onClick={(event) => {
                        event.preventDefault();
                        void loadDirectory(path, { push: true, force: false });
                      }}
                      className="text-accent"
                    >
                      {part}
                    </a>
                  </span>
                );
              })}
            </div>
            <div className="text-sm text-muted">{status}</div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="primary"
              className="h-10 gap-2"
              onClick={() => {
                uploadInputRef.current?.click();
              }}
            >
              <Upload className="h-4 w-4" />上传 PDF
            </Button>
            <input
              ref={uploadInputRef}
              type="file"
              accept=".pdf,application/pdf"
              multiple
              className="hidden"
              onChange={(event) => {
                const selected = Array.from(event.target.files || []);
                void submitUploads(selected);
              }}
            />

            <Button
              variant="danger"
              className="h-10 gap-2"
              disabled={selectedCount === 0}
              onClick={() => {
                void deleteSelected(Array.from(selectedPaths));
              }}
            >
              <Trash2 className="h-4 w-4" />删除所选{selectedCount > 0 ? ` (${selectedCount})` : ""}
            </Button>

            <Button variant="ghost" className="h-10 gap-2" onClick={() => void triggerRescan()}>
              <ScanSearch className="h-4 w-4" />重扫当前目录
            </Button>

            <Button variant="ghost" className="h-10 gap-2" onClick={() => void refreshCurrentDirectory()}>
              <RefreshCw className="h-4 w-4" />刷新
            </Button>
          </div>

          <form className="flex flex-wrap items-center gap-2" onSubmit={createFolder}>
            <div className="text-sm text-muted">创建子目录</div>
            <Input
              value={folderName}
              onChange={(event) => setFolderName(event.target.value)}
              placeholder="例如：engine"
              className="max-w-[260px]"
            />
            <Button variant="ghost" type="submit" className="h-10 gap-2">
              <FolderPlus className="h-4 w-4" />创建
            </Button>
          </form>

          {actionResult ? (
            <div className={`text-sm ${actionError ? "text-danger" : "text-muted"}`}>{actionResult}</div>
          ) : null}

          {files.length === 0 ? (
            <EmptyState title="无 PDF 文件" />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <TH className="w-[48px]">
                      <input
                        type="checkbox"
                        aria-label="全选文件"
                        checked={selectAllChecked}
                        onChange={(event) => toggleSelectAll(event.target.checked)}
                      />
                    </TH>
                    <TH>文件名</TH>
                    <TH>入库状态</TH>
                    <TH>任务状态</TH>
                    <TH>单文件操作</TH>
                  </tr>
                </thead>
                <tbody>
                  {files.map((file) => {
                    const rel = normalizeDir(file.relative_path || file.name || "");
                    const indexed = Boolean(file.indexed);
                    const taskStatus = jobStatusByPathRef.current.get(rel) || "queued";
                    const checked = selectedPaths.has(rel);
                    return (
                      <tr key={rel || file.name}>
                        <TD>
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={!rel}
                            onChange={() => toggleSelect(rel)}
                          />
                        </TD>
                        <TD className="font-mono text-xs break-all">{rel || "-"}</TD>
                        <TD>
                          <Badge variant={indexed ? "ok" : "neutral"}>{indexed ? "indexed" : "pending"}</Badge>
                        </TD>
                        <TD>
                          <Badge variant={taskStatus === "success" ? "ok" : taskStatus === "failed" ? "bad" : "neutral"}>
                            {taskStatus}
                          </Badge>
                        </TD>
                        <TD>
                          <Button
                            variant="ghost"
                            className="h-8"
                            disabled={!rel}
                            onClick={() => {
                              void deleteSelected([rel]);
                            }}
                          >
                            删除
                          </Button>
                        </TD>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
            </TableWrap>
          )}

          <div className="mt-1 text-sm font-medium">任务状态</div>
          {jobs.length === 0 ? (
            <p className="text-sm text-muted">暂无任务</p>
          ) : (
            <div className="grid gap-2">
              {jobs.slice(0, 20).map((job) => (
                <div key={job.rowId} className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface p-3">
                  <div className="min-w-0">
                    <div className="truncate font-mono text-xs text-text">{job.pathText}</div>
                    <div className="text-xs text-muted">
                      {job.kind} · {job.status}
                    </div>
                    {job.error ? <div className="truncate text-xs text-danger">{job.error}</div> : null}
                  </div>
                  <Badge variant={job.status === "success" ? "ok" : job.status === "failed" ? "bad" : "neutral"}>
                    {job.status === "running" ? <LoaderCircle className="mr-1 h-3 w-3 animate-spin" /> : null}
                    {job.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
