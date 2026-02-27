import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Card } from "@/components/ui/Card";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { fetchJson } from "@/lib/api";
import type { CapabilitiesResponse } from "@/lib/types";
import { dbPathFromUrl } from "@/lib/urlState";
import { DbDirectoryTreePanel } from "@/pages/db/DbDirectoryTreePanel";
import { DbFileTable } from "@/pages/db/DbFileTable";
import { DbJobsPanel } from "@/pages/db/DbJobsPanel";
import { DbToolbarPanel } from "@/pages/db/DbToolbarPanel";
import { useDbDirectoryModel } from "@/pages/db/useDbDirectoryModel";
import { useDbJobsPolling } from "@/pages/db/useDbJobsPolling";
import { useDbOperations } from "@/pages/db/useDbOperations";

export function DbPage() {
  const [folderName, setFolderName] = useState("");
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
    <AppShell actions={[{ href: "/search", label: "搜索", icon: <MaterialSymbol name="search" size={18} /> }]}>
      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <DbDirectoryTreePanel
          currentPath={directory.currentPath}
          treeCache={directory.treeCache}
          expandedDirs={directory.expandedDirs}
          onRefresh={() => void directory.refreshCurrentDirectory()}
          onLoadDirectory={(path) => void directory.loadDirectory(path, { push: true, force: false })}
          onToggleExpand={directory.toggleExpandDir}
          onEnsureTreeNode={async (path) => {
            await directory.ensureTreeNode(path);
          }}
        />

        <div className="grid min-w-0 gap-3">
          <Card className="grid min-w-0 gap-3">
            <DbToolbarPanel
              breadcrumbParts={directory.breadcrumbParts}
              status={directory.status}
              selectedCount={directory.selectedCount}
              folderName={folderName}
              onFolderNameChange={setFolderName}
              capabilities={capabilities}
              importDisabledReason={importDisabledReason}
              scanDisabledReason={scanDisabledReason}
              actionFeedback={operations.actionFeedback}
              onNavigate={(path) => void directory.loadDirectory(path, { push: true, force: false })}
              onUploadFiles={(selected) => void operations.submitUploads(selected)}
              onDeleteSelected={() => void operations.deleteSelected(Array.from(directory.selectedPaths))}
              onTriggerRescan={() => void operations.triggerRescan()}
              onRefresh={() => void directory.refreshCurrentDirectory()}
              onCreateFolder={() =>
                void operations.createFolder(folderName, () => {
                  setFolderName("");
                })
              }
            />

            <DbFileTable
              files={directory.files}
              selectedPaths={directory.selectedPaths}
              selectAllChecked={directory.selectAllChecked}
              knownDirectories={directory.knownDirectories}
              jobStatusByPath={polling.jobStatusByPath}
              capabilitiesImportEnabled={capabilities.import_enabled}
              importDisabledReason={importDisabledReason}
              getRowActionState={operations.rowActions.getRowActionState}
              onSetRowActionState={operations.rowActions.setRowActionState}
              onClearRowActionState={operations.rowActions.clearRowActionState}
              onToggleSelect={directory.toggleSelect}
              onToggleSelectAll={directory.toggleSelectAll}
              onBeginRename={operations.rowActions.beginRename}
              onBeginMove={operations.rowActions.beginMove}
              onApplyRename={(path) => void operations.rowActions.applyRename(path)}
              onApplyMove={(path) => void operations.rowActions.applyMove(path)}
              onDeleteSingle={(path) => void operations.deleteSelected([path])}
            />
          </Card>

          <DbJobsPanel jobs={polling.jobs} />
        </div>
      </div>
    </AppShell>
  );
}
