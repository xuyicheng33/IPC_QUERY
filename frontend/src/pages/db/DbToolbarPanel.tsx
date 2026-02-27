import React, { FormEvent, useRef } from "react";
import { Alert, Box, Typography } from "@mui/material";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { buildDbUrl } from "@/lib/urlState";
import type { CapabilitiesResponse, DbActionPhase } from "@/lib/types";

type DbToolbarPanelProps = {
  breadcrumbParts: string[];
  status: string;
  selectedCount: number;
  folderName: string;
  onFolderNameChange: (value: string) => void;
  capabilities: CapabilitiesResponse;
  importDisabledReason: string;
  scanDisabledReason: string;
  actionFeedback: { phase: DbActionPhase; message: string } | null;
  onNavigate: (path: string) => void;
  onUploadFiles: (files: File[]) => void;
  onDeleteSelected: () => void;
  onTriggerRescan: () => void;
  onRefresh: () => void;
  onCreateFolder: () => void;
};

export function DbToolbarPanel({
  breadcrumbParts,
  status,
  selectedCount,
  folderName,
  onFolderNameChange,
  capabilities,
  importDisabledReason,
  scanDisabledReason,
  actionFeedback,
  onNavigate,
  onUploadFiles,
  onDeleteSelected,
  onTriggerRescan,
  onRefresh,
  onCreateFolder,
}: DbToolbarPanelProps) {
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  const submitCreateFolder = (event: FormEvent) => {
    event.preventDefault();
    onCreateFolder();
  };

  return (
    <>
      <Box display="flex" flexWrap="wrap" alignItems="center" justifyContent="space-between" gap={1}>
        <Box className="font-mono text-xs">
          <a
            href="/db"
            onClick={(event) => {
              event.preventDefault();
              onNavigate("");
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
                    onNavigate(path);
                  }}
                  className="text-accent"
                >
                  {part}
                </a>
              </span>
            );
          })}
        </Box>
        <Typography variant="body2" color="text.secondary">
          {status}
        </Typography>
      </Box>

      <Box display="flex" flexWrap="wrap" alignItems="center" gap={1}>
        <Button
          variant="primary"
          className="h-10 gap-2"
          disabled={!capabilities.import_enabled}
          title={capabilities.import_enabled ? "上传 PDF" : importDisabledReason}
          startIcon={<MaterialSymbol name="upload_file" size={18} />}
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
          variant="danger"
          className="h-10 gap-2"
          disabled={!capabilities.import_enabled || selectedCount === 0}
          title={capabilities.import_enabled ? undefined : importDisabledReason}
          startIcon={<MaterialSymbol name="delete" size={18} />}
          onClick={onDeleteSelected}
        >
          删除所选{selectedCount > 0 ? ` (${selectedCount})` : ""}
        </Button>

        <Button
          variant="ghost"
          className="h-10 gap-2"
          disabled={!capabilities.scan_enabled}
          title={capabilities.scan_enabled ? undefined : scanDisabledReason}
          startIcon={<MaterialSymbol name="scan" size={18} />}
          onClick={onTriggerRescan}
        >
          重扫当前目录
        </Button>

        <Button variant="ghost" className="h-10 gap-2" startIcon={<MaterialSymbol name="refresh" size={18} />} onClick={onRefresh}>
          刷新
        </Button>
      </Box>

      <form className="flex flex-wrap items-center gap-2" onSubmit={submitCreateFolder}>
        <Typography variant="body2" color="text.secondary">
          创建子目录
        </Typography>
        <Input
          value={folderName}
          onChange={(event) => onFolderNameChange(event.target.value)}
          placeholder="例如：engine"
          className="max-w-[260px]"
          disabled={!capabilities.import_enabled}
        />
        <Button
          variant="ghost"
          type="submit"
          className="h-10 gap-2"
          disabled={!capabilities.import_enabled}
          title={capabilities.import_enabled ? undefined : importDisabledReason}
          startIcon={<MaterialSymbol name="create_new_folder" size={18} />}
        >
          创建
        </Button>
      </form>

      {actionFeedback ? (
        <Alert
          severity={actionFeedback.phase === "error" ? "error" : actionFeedback.phase === "pending" ? "info" : "success"}
          variant="outlined"
        >
          {actionFeedback.message}
        </Alert>
      ) : null}
    </>
  );
}
