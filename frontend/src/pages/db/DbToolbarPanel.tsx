import React, { FormEvent, useRef, useState } from "react";
import { Box, Dialog, DialogActions, DialogContent, DialogTitle } from "@mui/material";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { buildDbUrl } from "@/lib/urlState";
import type { CapabilitiesResponse } from "@/lib/types";

type DbToolbarPanelProps = {
  currentPath: string;
  breadcrumbParts: string[];
  directoryCount: number;
  status: string;
  selectedCount: number;
  fileCount: number;
  folderName: string;
  onFolderNameChange: (value: string) => void;
  capabilities: CapabilitiesResponse;
  importDisabledReason: string;
  onNavigate: (path: string) => void;
  onUploadFiles: (files: File[]) => void;
  onDeleteSelected: () => void;
  onRefresh: () => void;
  onCreateFolder: () => void;
};

export function DbToolbarPanel({
  currentPath,
  breadcrumbParts,
  directoryCount,
  status,
  selectedCount,
  fileCount,
  folderName,
  onFolderNameChange,
  capabilities,
  importDisabledReason,
  onNavigate,
  onUploadFiles,
  onDeleteSelected,
  onRefresh,
  onCreateFolder,
}: DbToolbarPanelProps) {
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const createFolderDisabled = !capabilities.import_enabled || currentPath !== "";
  const allowBatchDelete = capabilities.import_enabled && selectedCount > 0;
  const createFolderHint = capabilities.import_enabled
    ? currentPath
      ? "仅支持在根目录创建子目录"
      : ""
    : importDisabledReason;
  const createFolderCanSubmit = !createFolderDisabled && Boolean(folderName.trim());

  const submitCreateFolder = (event: FormEvent) => {
    event.preventDefault();
    if (!createFolderCanSubmit) return;
    onCreateFolder();
    setCreateDialogOpen(false);
  };

  return (
    <div className="grid gap-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <Box className="flex flex-wrap items-center gap-2 text-sm text-text">
            <a
              href="/db.html"
              onClick={(event) => {
                event.preventDefault();
                onNavigate("");
              }}
              className="inline-flex items-center gap-1 rounded-sm px-1 py-0.5 hover:bg-surface-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            >
              <MaterialSymbol name="folder" size={16} />
              根目录
            </a>
            {breadcrumbParts.map((part, index) => {
              const path = breadcrumbParts.slice(0, index + 1).join("/");
              return (
                <React.Fragment key={path}>
                  <MaterialSymbol name="chevron_right" size={14} className="text-muted" />
                  <a
                    href={buildDbUrl(path)}
                    onClick={(event) => {
                      event.preventDefault();
                      onNavigate(path);
                    }}
                    className="inline-flex items-center rounded-sm px-1 py-0.5 hover:bg-surface-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                  >
                    {part}
                  </a>
                </React.Fragment>
              );
            })}
          </Box>
          <div className="mt-1 text-xs text-muted">
            目录 {directoryCount} · 文件 {fileCount}
            {` · 已选 ${selectedCount}`}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 lg:justify-end">
          <Button
            variant="primary"
            className="h-10 gap-1.5 px-4"
            disabled={!capabilities.import_enabled}
            title={capabilities.import_enabled ? "上传 PDF" : importDisabledReason}
            startIcon={<MaterialSymbol name="upload_file" size={16} />}
            onClick={() => uploadInputRef.current?.click()}
          >
            上传 PDF
          </Button>
          <input
            ref={uploadInputRef}
            type="file"
            accept=".pdf,application/pdf"
            multiple
            className="hidden"
            onChange={(event) => {
              onUploadFiles(Array.from(event.target.files || []));
              event.currentTarget.value = "";
            }}
          />

          <Button
            variant="ghost"
            type="button"
            className="h-10 gap-1.5 px-4"
            disabled={createFolderDisabled}
            title={createFolderHint || "创建子目录"}
            startIcon={<MaterialSymbol name="create_new_folder" size={16} />}
            onClick={() => setCreateDialogOpen(true)}
          >
            创建子目录
          </Button>

          <Button
            variant="danger"
            className="h-10 gap-1.5 px-4"
            disabled={!allowBatchDelete}
            title={capabilities.import_enabled ? undefined : importDisabledReason}
            startIcon={<MaterialSymbol name="delete" size={16} />}
            onClick={onDeleteSelected}
          >
            删除所选{selectedCount > 0 ? ` (${selectedCount})` : ""}
          </Button>

          <Button variant="ghost" className="h-10 gap-1.5 px-4" startIcon={<MaterialSymbol name="refresh" size={16} />} onClick={onRefresh}>
            刷新
          </Button>
        </div>
      </div>

      {status ? <div className="rounded-md border border-border bg-surface-soft px-3 py-2 text-xs text-muted">{status}</div> : null}

      <Dialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        fullWidth
        maxWidth="xs"
        aria-labelledby="db-create-folder-title"
      >
        <form onSubmit={submitCreateFolder}>
          <DialogTitle id="db-create-folder-title">新建子目录</DialogTitle>
          <DialogContent>
            <Input
              id="db-folder-name"
              name="folder_name"
              value={folderName}
              onChange={(event) => onFolderNameChange(event.target.value)}
              placeholder="填写新建子目录名称"
              className="mt-2 w-full"
              disabled={createFolderDisabled}
              aria-label="新建子目录名称"
              autoFocus
            />
            {createFolderHint ? <p className="mt-2 text-xs text-muted">{createFolderHint}</p> : null}
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2.5 }}>
            <Button variant="ghost" type="button" onClick={() => setCreateDialogOpen(false)}>
              取消
            </Button>
            <Button variant="ghost" type="submit" disabled={!createFolderCanSubmit}>
              创建
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </div>
  );
}
