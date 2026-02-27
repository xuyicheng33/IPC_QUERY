import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Snackbar, useMediaQuery } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { AppShell } from "@/components/layout/AppShell";
import { Card } from "@/components/ui/Card";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
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
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
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

  useEffect(() => {
    if (operations.actionFeedback?.message) {
      setToastOpen(true);
    }
  }, [operations.actionFeedback]);

  useEffect(() => {
    if (!isMobile) return;
    if (directory.selectedCount === 0) return;
    directory.clearSelection();
  }, [directory.clearSelection, directory.selectedCount, isMobile]);

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
    <AppShell actions={[{ href: "/search", label: "搜索", icon: <MaterialSymbol name="search" size={18} /> }]} hideHeaderTitle>
      <div className="grid gap-4">
        <Card className="grid min-w-0 gap-4 p-4">
          <DbToolbarPanel
            currentPath={directory.currentPath}
            breadcrumbParts={directory.breadcrumbParts}
            directoryCount={directory.directories.length}
            status={directory.status}
            selectedCount={directory.selectedCount}
            fileCount={directory.files.length}
            isMobile={isMobile}
            folderName={folderName}
            onFolderNameChange={setFolderName}
            capabilities={capabilities}
            importDisabledReason={importDisabledReason}
            onNavigate={(path) => void directory.loadDirectory(path, { push: true, force: false })}
            onUploadFiles={(selected) => void operations.submitUploads(selected)}
            onDeleteSelected={() => void operations.deleteSelected(Array.from(directory.selectedPaths))}
            onRefresh={() => void directory.refreshCurrentDirectory()}
            onCreateFolder={() =>
              void operations.createFolder(folderName, () => {
                setFolderName("");
              })
            }
          />

          <DbFileTable
            items={listItems}
            isMobile={isMobile}
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
            onDeleteSingle={(path) => void operations.deleteSelected([path])}
            onOpenDirectory={(path) => void directory.loadDirectory(path, { push: true, force: false })}
          />
        </Card>
      </div>
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
    </AppShell>
  );
}
