import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Dialog, DialogActions, DialogContent, DialogTitle, Snackbar } from "@mui/material";
import { Button } from "@/components/ui/Button";
import { DesktopShell } from "@/components/layout/DesktopShell";
import { Card } from "@/components/ui/Card";
import { fetchJson } from "@/lib/api";
import type { CapabilitiesResponse, DbListItem } from "@/lib/types";
import { dbPathFromUrl } from "@/lib/urlState";
import { DbFileTable } from "@/pages/db/DbFileTable";
import { DbToolbarPanel } from "@/pages/db/DbToolbarPanel";
import { useDbDirectoryModel } from "@/pages/db/useDbDirectoryModel";
import { useDbJobsPolling } from "@/pages/db/useDbJobsPolling";
import { useDbOperations } from "@/pages/db/useDbOperations";

export function DbPage() {
  const [folderName, setFolderName] = useState("");
  const [toastOpen, setToastOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteTargets, setDeleteTargets] = useState<string[]>([]);
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse>({
    import_enabled: true,
    scan_enabled: true,
    import_reason: "",
    scan_reason: "",
  });

  const directory = useDbDirectoryModel({ initialPath: dbPathFromUrl(window.location.search) });
  const setDirectoryStatus = directory.setStatus;
  const importDisabledReason = capabilities.import_enabled
    ? ""
    : String(capabilities.import_reason || "导入服务不可用");
  const scanDisabledReason = capabilities.scan_enabled
    ? ""
    : String(capabilities.scan_reason || "重扫服务不可用");
  const loadCapabilities = useCallback(async () => {
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
      setDirectoryStatus(`加载能力信息失败：${message}`);
    }
  }, [setDirectoryStatus]);

  const polling = useDbJobsPolling({
    onAllJobsSettled: async () => {
      await directory.refreshCurrentDirectory();
    },
  });

  const operations = useDbOperations({
    currentPath: directory.currentPath,
    visibleFiles: directory.files,
    capabilities,
    importDisabledReason,
    scanDisabledReason,
    refreshCurrentDirectory: directory.refreshCurrentDirectory,
    clearSelection: directory.clearSelection,
    setStatus: directory.setStatus,
    upsertJob: polling.upsertJob,
    startImportJob: polling.startImportJob,
    startScanJob: polling.startScanJob,
  });
  const listItems = useMemo<DbListItem[]>(() => {
    const directoryItems = directory.directories.map((dir) => {
      const name = String(dir.name || dir.path || "").split("/").pop() || dir.path || "-";
      return {
        name,
        relative_path: dir.path,
        indexed: true,
        is_dir: true,
      };
    });
    const fileItems = directory.files.map((file) => ({
      ...file,
      is_dir: false,
    }));
    return [...directoryItems, ...fileItems];
  }, [directory.directories, directory.files]);
  const deletePreview = useMemo(() => deleteTargets.slice(0, 6), [deleteTargets]);

  const requestDelete = useCallback((paths: string[]) => {
    const list = paths.map((path) => String(path || "").trim()).filter(Boolean);
    if (list.length === 0) return;
    setDeleteTargets(list);
    setDeleteDialogOpen(true);
  }, []);

  const closeDeleteDialog = useCallback(() => {
    setDeleteDialogOpen(false);
    setDeleteTargets([]);
  }, []);

  const confirmDelete = useCallback(async () => {
    const paths = [...deleteTargets];
    closeDeleteDialog();
    if (paths.length === 0) return;
    await operations.deleteSelected(paths);
  }, [closeDeleteDialog, deleteTargets, operations]);

  useEffect(() => {
    if (operations.actionFeedback?.message) {
      setToastOpen(true);
    }
  }, [operations.actionFeedback]);

  useEffect(() => {
    const onPopState = () => {
      void directory.loadDirectory(dbPathFromUrl(window.location.search), { push: false, force: false });
    };

    window.addEventListener("popstate", onPopState);
    void loadCapabilities();
    void directory.loadDirectory(dbPathFromUrl(window.location.search), { push: false, force: true });

    return () => {
      window.removeEventListener("popstate", onPopState);
      polling.stopAllPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <DesktopShell actions={[{ href: "/search.html", label: "搜索" }]} hideHeaderTitle>
      <div className="grid gap-4">
        <Card className="grid min-w-0 gap-4 p-4">
          <DbToolbarPanel
            currentPath={directory.currentPath}
            breadcrumbParts={directory.breadcrumbParts}
            directoryCount={directory.directories.length}
            status={directory.status}
            selectedCount={directory.selectedCount}
            fileCount={directory.files.length}
            folderName={folderName}
            onFolderNameChange={setFolderName}
            capabilities={capabilities}
            importDisabledReason={importDisabledReason}
            onNavigate={(path) => void directory.loadDirectory(path, { push: true, force: false })}
            onUploadFiles={(selected) => void operations.submitUploads(selected)}
            onDeleteSelected={() => requestDelete(Array.from(directory.selectedPaths))}
            onRefresh={() => void directory.refreshCurrentDirectory()}
            onCreateFolder={() =>
              void operations.createFolder(folderName, () => {
                setFolderName("");
              })
            }
          />

          <DbFileTable
            items={listItems}
            selectedPaths={directory.selectedPaths}
            onSelectionChange={directory.setSelection}
            knownDirectories={directory.knownDirectories}
            capabilitiesImportEnabled={capabilities.import_enabled}
            importDisabledReason={importDisabledReason}
            getRowActionState={operations.rowActions.getRowActionState}
            onSetRowActionState={operations.rowActions.setRowActionState}
            onClearRowActionState={operations.rowActions.clearRowActionState}
            onBeginRename={operations.rowActions.beginRename}
            onBeginMove={operations.rowActions.beginMove}
            onApplyRename={(path) => void operations.rowActions.applyRename(path)}
            onApplyMove={(path) => void operations.rowActions.applyMove(path)}
            onDeleteSingle={(path) => requestDelete([path])}
            onOpenDirectory={(path) => void directory.loadDirectory(path, { push: true, force: false })}
          />
        </Card>
      </div>
      <Dialog open={deleteDialogOpen} onClose={closeDeleteDialog} fullWidth maxWidth="sm" aria-labelledby="db-delete-dialog-title">
        <DialogTitle id="db-delete-dialog-title">确认删除</DialogTitle>
        <DialogContent>
          <div className="mt-1 text-sm text-text">将删除 {deleteTargets.length} 个文件，对应数据库记录和磁盘文件都会被移除。</div>
          <div className="mt-3 rounded-md border border-border bg-surface-soft px-3 py-2">
            <div className="text-xs text-muted">示例路径：</div>
            <ul className="mt-1 space-y-1 text-xs text-text">
              {deletePreview.map((path) => (
                <li key={path} className="font-mono">
                  {path}
                </li>
              ))}
              {deleteTargets.length > deletePreview.length ? <li className="text-muted">...</li> : null}
            </ul>
          </div>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button variant="ghost" onClick={closeDeleteDialog}>
            取消
          </Button>
          <Button variant="danger" onClick={() => void confirmDelete()}>
            确认删除
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar
        open={toastOpen}
        autoHideDuration={2800}
        onClose={() => setToastOpen(false)}
        anchorOrigin={{ vertical: "top", horizontal: "right" }}
      >
        <Alert
          onClose={() => setToastOpen(false)}
          severity={
            operations.actionFeedback?.phase === "error"
              ? "error"
              : operations.actionFeedback?.phase === "pending"
                ? "info"
                : "success"
          }
          variant="filled"
        >
          {operations.actionFeedback?.message || "操作完成"}
        </Alert>
      </Snackbar>
    </DesktopShell>
  );
}
