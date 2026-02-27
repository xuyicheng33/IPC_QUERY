import React, { useMemo, useState } from "react";
import { Box, CircularProgress } from "@mui/material";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { Select } from "@/components/ui/Select";
import type { DbListItem, DbRowActionState } from "@/lib/types";
import { normalizeDir } from "@/lib/urlState";

type DbFileTableProps = {
  items: DbListItem[];
  selectedPaths: Set<string>;
  selectAllChecked: boolean;
  knownDirectories: string[];
  capabilitiesImportEnabled: boolean;
  importDisabledReason: string;
  getRowActionState: (path: string) => DbRowActionState;
  onSetRowActionState: (path: string, state: DbRowActionState) => void;
  onClearRowActionState: (path: string) => void;
  onToggleSelect: (path: string) => void;
  onToggleSelectAll: (checked: boolean) => void;
  onBeginRename: (path: string) => void;
  onBeginMove: (path: string) => void;
  onApplyRename: (path: string) => void;
  onApplyMove: (path: string) => void;
  onDeleteSingle: (path: string) => void;
  onOpenDirectory: (path: string) => void;
};

export function DbFileTable({
  items,
  selectedPaths,
  selectAllChecked,
  knownDirectories,
  capabilitiesImportEnabled,
  importDisabledReason,
  getRowActionState,
  onSetRowActionState,
  onClearRowActionState,
  onToggleSelect,
  onToggleSelectAll,
  onBeginRename,
  onBeginMove,
  onApplyRename,
  onApplyMove,
  onDeleteSingle,
  onOpenDirectory,
}: DbFileTableProps) {
  const [activeDirectoryPath, setActiveDirectoryPath] = useState("");
  const hasFiles = useMemo(() => items.some((item) => !item.is_dir), [items]);

  if (items.length === 0) {
    return <EmptyState title="空目录" />;
  }

  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border bg-surface-soft px-3 py-2 text-xs text-muted">
        <label className="inline-flex select-none items-center gap-2">
          <input
            type="checkbox"
            aria-label="全选文件"
            checked={hasFiles ? selectAllChecked : false}
            disabled={!hasFiles}
            onChange={(event) => onToggleSelectAll(event.target.checked)}
          />
          全选文件
        </label>
        <span>双击文件夹进入</span>
      </div>

      <div>
        {items.map((item) => {
          const rel = normalizeDir(item.relative_path || item.name || "");
          const checked = selectedPaths.has(rel);
          const actionState = getRowActionState(rel);
          const moveTarget = normalizeDir(actionState.value || "");
          const previewHref = `/viewer.html?pdf=${encodeURIComponent(rel)}&page=1`;
          const pending = actionState.phase === "pending";
          const isDirectory = item.is_dir;
          const isActiveDirectory = isDirectory && activeDirectoryPath === rel;

          return (
            <div
              key={rel || item.name}
              className={`group flex items-center gap-2 border-b border-border px-3 py-2 last:border-b-0 ${
                isDirectory ? "cursor-pointer" : ""
              } ${isActiveDirectory ? "bg-accent-soft" : "hover:bg-surface-soft"}`}
              onClick={() => {
                if (isDirectory) setActiveDirectoryPath(rel);
              }}
              onDoubleClick={() => {
                if (isDirectory) onOpenDirectory(rel);
              }}
            >
              <div className="flex w-7 items-center justify-center">
                {isDirectory ? (
                  <MaterialSymbol name="folder" size={20} className="text-accent" />
                ) : (
                  <input type="checkbox" checked={checked} disabled={!rel} onChange={() => onToggleSelect(rel)} />
                )}
              </div>

              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-text">{item.name || rel || "-"}</div>
                <div className="truncate font-mono text-xs text-muted">{rel || "-"}</div>
              </div>

              <div className="min-w-[320px]">
                {isDirectory ? (
                  <div className="flex justify-end">
                    <Button variant="ghost" className="h-8 gap-1.5 px-2" onClick={() => onOpenDirectory(rel)}>
                      进入
                    </Button>
                  </div>
                ) : actionState.mode === "renaming" ? (
                  <div className="grid gap-1">
                    <div className="flex items-center gap-1">
                      <Input
                        value={actionState.value}
                        onChange={(event) =>
                          onSetRowActionState(rel, { ...actionState, value: event.target.value, error: "", phase: "idle" })
                        }
                        className="h-8"
                        placeholder="新文件名，如 b.pdf"
                        disabled={pending}
                      />
                      <Button
                        variant="ghost"
                        className="h-8 min-w-8 px-2"
                        onClick={() => onApplyRename(rel)}
                        disabled={pending}
                        startIcon={pending ? <CircularProgress size={14} /> : <MaterialSymbol name="check" size={16} />}
                      />
                      <Button
                        variant="ghost"
                        className="h-8 min-w-8 px-2"
                        onClick={() => onClearRowActionState(rel)}
                        disabled={pending}
                        startIcon={<MaterialSymbol name="close" size={16} />}
                      />
                    </div>
                    {actionState.error ? <div className="text-xs text-danger">{actionState.error}</div> : null}
                  </div>
                ) : actionState.mode === "moving" ? (
                  <div className="grid gap-1">
                    <div className="flex items-center gap-1">
                      <Select
                        value={moveTarget}
                        className="h-8"
                        onChange={(event) =>
                          onSetRowActionState(rel, {
                            ...actionState,
                            value: normalizeDir(event.target.value),
                            error: "",
                            phase: "idle",
                          })
                        }
                        disabled={pending}
                      >
                        {knownDirectories.map((dir) => (
                          <option key={dir || "root"} value={dir}>
                            {dir || "/"}
                          </option>
                        ))}
                      </Select>
                      <Button
                        variant="ghost"
                        className="h-8 min-w-8 px-2"
                        onClick={() => onApplyMove(rel)}
                        disabled={pending}
                        startIcon={pending ? <CircularProgress size={14} /> : <MaterialSymbol name="check" size={16} />}
                      />
                      <Button
                        variant="ghost"
                        className="h-8 min-w-8 px-2"
                        onClick={() => onClearRowActionState(rel)}
                        disabled={pending}
                        startIcon={<MaterialSymbol name="close" size={16} />}
                      />
                    </div>
                    {actionState.error ? <div className="text-xs text-danger">{actionState.error}</div> : null}
                  </div>
                ) : (
                  <Box
                    display="flex"
                    justifyContent="flex-end"
                    alignItems="center"
                    gap={0.5}
                    className="opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100"
                  >
                    <a href={previewHref} target="_blank" rel="noreferrer">
                      <Button variant="ghost" className="h-8 gap-1.5 px-2" disabled={!rel} startIcon={<MaterialSymbol name="open_in_new" size={16} />}>
                        预览
                      </Button>
                    </a>
                    <Button
                      variant="ghost"
                      className="h-8 gap-1.5 px-2"
                      disabled={!rel || !capabilitiesImportEnabled}
                      title={capabilitiesImportEnabled ? undefined : importDisabledReason}
                      startIcon={<MaterialSymbol name="edit" size={16} />}
                      onClick={() => onBeginRename(rel)}
                    >
                      改名
                    </Button>
                    <Button
                      variant="ghost"
                      className="h-8 gap-1.5 px-2"
                      disabled={!rel || !capabilitiesImportEnabled}
                      title={capabilitiesImportEnabled ? undefined : importDisabledReason}
                      startIcon={<MaterialSymbol name="drive_file_move" size={16} />}
                      onClick={() => onBeginMove(rel)}
                    >
                      移动
                    </Button>
                    <Button
                      variant="ghost"
                      className="h-8 gap-1.5 px-2 text-danger"
                      disabled={!rel || !capabilitiesImportEnabled}
                      title={capabilitiesImportEnabled ? undefined : importDisabledReason}
                      startIcon={<MaterialSymbol name="delete" size={16} />}
                      onClick={() => {
                        if (window.confirm(`确认删除 ${rel}？此操作不可撤销。`)) {
                          onDeleteSingle(rel);
                        }
                      }}
                    >
                      删除
                    </Button>
                  </Box>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
