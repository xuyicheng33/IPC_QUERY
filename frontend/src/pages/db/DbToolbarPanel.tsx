import React, { FormEvent, useRef } from "react";
import { Box } from "@mui/material";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { buildDbUrl } from "@/lib/urlState";
import type { CapabilitiesResponse } from "@/lib/types";

type DbToolbarPanelProps = {
  currentPath: string;
  breadcrumbParts: string[];
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
  const createFolderDisabled = !capabilities.import_enabled || currentPath !== "";

  const submitCreateFolder = (event: FormEvent) => {
    event.preventDefault();
    onCreateFolder();
  };

  return (
    <div className="grid gap-3">
      <Box className="flex flex-wrap items-center gap-2 text-sm text-text">
        <a
          href="/db"
          onClick={(event) => {
            event.preventDefault();
            onNavigate("");
          }}
          className="inline-flex items-center gap-1 rounded-sm px-1 py-0.5 hover:bg-surface-soft"
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
                className="inline-flex items-center rounded-sm px-1 py-0.5 hover:bg-surface-soft"
              >
                {part}
              </a>
            </React.Fragment>
          );
        })}
        <span className="ml-2 text-xs text-muted">文件 {fileCount} · 已选 {selectedCount}</span>
      </Box>

      <div className="rounded-md border border-border bg-surface-soft px-3 py-2 text-xs text-muted">
        {status || `目录 ${currentPath || "/"} · 文件 ${fileCount}`}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="primary"
          className="h-9 gap-1.5 px-3"
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

        <form className="flex flex-wrap items-center gap-2" onSubmit={submitCreateFolder}>
          <Input
            value={folderName}
            onChange={(event) => onFolderNameChange(event.target.value)}
            placeholder={currentPath ? "仅根目录可创建子目录" : "新建子目录名称"}
            className="h-9 w-[220px]"
            disabled={createFolderDisabled}
          />
          <Button
            variant="ghost"
            type="submit"
            className="h-9 gap-1.5 px-3"
            disabled={createFolderDisabled || !folderName.trim()}
            title={capabilities.import_enabled ? (currentPath ? "仅支持在根目录创建子目录" : undefined) : importDisabledReason}
            startIcon={<MaterialSymbol name="create_new_folder" size={16} />}
          >
            创建子目录
          </Button>
        </form>

        <Button
          variant="danger"
          className="h-9 gap-1.5 px-3"
          disabled={!capabilities.import_enabled || selectedCount === 0}
          title={capabilities.import_enabled ? undefined : importDisabledReason}
          startIcon={<MaterialSymbol name="delete" size={16} />}
          onClick={() => {
            if (window.confirm(`确认删除已选的 ${selectedCount} 个文件？此操作不可撤销。`)) {
              onDeleteSelected();
            }
          }}
        >
          删除所选{selectedCount > 0 ? ` (${selectedCount})` : ""}
        </Button>

        <Button variant="ghost" className="h-9 gap-1.5 px-3" startIcon={<MaterialSymbol name="refresh" size={16} />} onClick={onRefresh}>
          刷新
        </Button>
      </div>
    </div>
  );
}
