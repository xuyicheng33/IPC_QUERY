import React, { KeyboardEvent, MouseEvent, useMemo, useState } from "react";
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
  isMobile: boolean;
  selectedPaths: Set<string>;
  onSelectionChange: (paths: string[]) => void;
  knownDirectories: string[];
  capabilitiesImportEnabled: boolean;
  importDisabledReason: string;
  getRowActionState: (path: string) => DbRowActionState;
  onSetRowActionState: (path: string, state: DbRowActionState) => void;
  onClearRowActionState: (path: string) => void;
  onBeginRename: (path: string) => void;
  onBeginMove: (path: string) => void;
  onApplyRename: (path: string) => void;
  onApplyMove: (path: string) => void;
  onDeleteSingle: (path: string) => void;
  onOpenDirectory: (path: string) => void;
};

export function DbFileTable({
  items,
  isMobile,
  selectedPaths,
  onSelectionChange,
  knownDirectories,
  capabilitiesImportEnabled,
  importDisabledReason,
  getRowActionState,
  onSetRowActionState,
  onClearRowActionState,
  onBeginRename,
  onBeginMove,
  onApplyRename,
  onApplyMove,
  onDeleteSingle,
  onOpenDirectory,
}: DbFileTableProps) {
  const [activeDirectoryPath, setActiveDirectoryPath] = useState("");
  const [anchorPath, setAnchorPath] = useState("");
  const orderedFilePaths = useMemo(
    () => items.filter((item) => !item.is_dir).map((item) => normalizeDir(item.relative_path || item.name || "")).filter(Boolean),
    [items]
  );

  const pushOrderedSelection = (next: Set<string>) => {
    onSelectionChange(orderedFilePaths.filter((path) => next.has(path)));
  };

  const applyFileSelection = (
    rel: string,
    modifier: { shift: boolean; toggle: boolean }
  ) => {
    if (isMobile || !rel) return;
    const next = new Set<string>(selectedPaths);

    if (modifier.shift) {
      const currentIndex = orderedFilePaths.indexOf(rel);
      const anchorIndex = orderedFilePaths.indexOf(anchorPath || rel);
      if (currentIndex >= 0 && anchorIndex >= 0) {
        const [start, end] = anchorIndex <= currentIndex ? [anchorIndex, currentIndex] : [currentIndex, anchorIndex];
        next.clear();
        for (let i = start; i <= end; i += 1) {
          next.add(orderedFilePaths[i]);
        }
      } else {
        next.clear();
        next.add(rel);
      }
      setAnchorPath(rel);
      pushOrderedSelection(next);
      return;
    }

    if (modifier.toggle) {
      if (next.has(rel)) next.delete(rel);
      else next.add(rel);
      setAnchorPath(rel);
      pushOrderedSelection(next);
      return;
    }

    next.clear();
    next.add(rel);
    setAnchorPath(rel);
    pushOrderedSelection(next);
  };

  if (items.length === 0) {
    return <EmptyState title="空目录" />;
  }

  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface">
      <div role="list" aria-label="数据库文件列表">
        {items.map((item) => {
          const rel = normalizeDir(item.relative_path || item.name || "");
          const actionState = getRowActionState(rel);
          const moveTarget = normalizeDir(actionState.value || "");
          const previewHref = `/viewer.html?pdf=${encodeURIComponent(rel)}&page=1`;
          const pending = actionState.phase === "pending";
          const isDirectory = item.is_dir;
          const isActiveDirectory = isDirectory && activeDirectoryPath === rel;
          const isSelected = !isDirectory && selectedPaths.has(rel);
          const displayName = String(item.name || rel || "-");
          const showRelativePath = Boolean(rel && rel !== displayName);

          const stopRowEvent = (event: MouseEvent<HTMLElement>) => {
            event.preventDefault();
            event.stopPropagation();
          };

          const handleFileClick = (event: MouseEvent<HTMLDivElement>) => {
            if (actionState.mode !== "normal") return;
            applyFileSelection(rel, {
              shift: event.shiftKey,
              toggle: event.metaKey || event.ctrlKey,
            });
          };

          const handleFileKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
            if (actionState.mode !== "normal") return;
            if (event.key === " " || event.key === "Enter") {
              event.preventDefault();
              applyFileSelection(rel, {
                shift: event.shiftKey,
                toggle: event.metaKey || event.ctrlKey,
              });
            }
          };

          return (
            <div
              key={rel || item.name}
              role={isDirectory ? "button" : undefined}
              aria-label={isDirectory ? `目录 ${displayName}` : `${displayName}${isSelected ? "（已选）" : ""}`}
              tabIndex={0}
              className={`group flex gap-2 border-b border-border px-3 py-2 last:border-b-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                isMobile && !isDirectory ? "flex-col items-stretch" : "items-center"
              } ${
                isDirectory || !isMobile ? "cursor-pointer" : ""
              } ${isDirectory && isActiveDirectory ? "bg-accent-soft" : isSelected ? "bg-accent-soft" : "hover:bg-surface-soft"}`}
              onClick={(event) => {
                if (isDirectory) {
                  if (isMobile) {
                    onOpenDirectory(rel);
                    return;
                  }
                  setActiveDirectoryPath(rel);
                  return;
                }
                handleFileClick(event);
              }}
              onDoubleClick={() => {
                if (isDirectory && !isMobile) onOpenDirectory(rel);
              }}
              onKeyDown={(event) => {
                if (isDirectory) {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onOpenDirectory(rel);
                  }
                  return;
                }
                handleFileKeyDown(event);
              }}
            >
              <div className="flex w-7 items-center justify-center">
                <MaterialSymbol name={isDirectory ? "folder" : "description"} size={20} className={isDirectory ? "text-accent" : "text-muted"} />
              </div>

              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-text">{displayName}</div>
                {showRelativePath ? <div className="truncate font-mono text-xs text-muted">{rel}</div> : null}
              </div>

              <div className={isMobile && !isDirectory ? "w-full" : "min-w-[170px] md:min-w-[320px]"}>
                {isDirectory ? (
                  <div className="flex justify-end text-muted">
                    <MaterialSymbol name="chevron_right" size={18} />
                  </div>
                ) : actionState.mode === "renaming" ? (
                  <div className="grid gap-1">
                    <div className="flex items-center gap-1">
                      <Input
                        name={`rename-${rel}`}
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
                        onClick={(event) => {
                          stopRowEvent(event);
                          onApplyRename(rel);
                        }}
                        disabled={pending}
                        startIcon={pending ? <CircularProgress size={14} /> : <MaterialSymbol name="check" size={16} />}
                      />
                      <Button
                        variant="ghost"
                        className="h-8 min-w-8 px-2"
                        onClick={(event) => {
                          stopRowEvent(event);
                          onClearRowActionState(rel);
                        }}
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
                        name={`move-${rel}`}
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
                        onClick={(event) => {
                          stopRowEvent(event);
                          onApplyMove(rel);
                        }}
                        disabled={pending}
                        startIcon={pending ? <CircularProgress size={14} /> : <MaterialSymbol name="check" size={16} />}
                      />
                      <Button
                        variant="ghost"
                        className="h-8 min-w-8 px-2"
                        onClick={(event) => {
                          stopRowEvent(event);
                          onClearRowActionState(rel);
                        }}
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
                    flexWrap={isMobile ? "wrap" : "nowrap"}
                    gap={0.5}
                    className={isMobile ? "opacity-100" : "opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100"}
                  >
                    <Button
                      variant="ghost"
                      className="h-8 gap-1.5 px-2"
                      disabled={!rel}
                      startIcon={<MaterialSymbol name="open_in_new" size={16} />}
                      onClick={(event) => {
                        stopRowEvent(event);
                        if (!rel) return;
                        window.open(previewHref, "_blank", "noopener,noreferrer");
                      }}
                    >
                      预览
                    </Button>
                    <Button
                      variant="ghost"
                      className="h-8 gap-1.5 px-2"
                      disabled={!rel || !capabilitiesImportEnabled}
                      title={capabilitiesImportEnabled ? undefined : importDisabledReason}
                      startIcon={<MaterialSymbol name="edit" size={16} />}
                      onClick={(event) => {
                        stopRowEvent(event);
                        onBeginRename(rel);
                      }}
                    >
                      改名
                    </Button>
                    <Button
                      variant="ghost"
                      className="h-8 gap-1.5 px-2"
                      disabled={!rel || !capabilitiesImportEnabled}
                      title={capabilitiesImportEnabled ? undefined : importDisabledReason}
                      startIcon={<MaterialSymbol name="drive_file_move" size={16} />}
                      onClick={(event) => {
                        stopRowEvent(event);
                        onBeginMove(rel);
                      }}
                    >
                      移动
                    </Button>
                    <Button
                      variant="ghost"
                      className="h-8 gap-1.5 px-2 text-danger"
                      disabled={!rel || !capabilitiesImportEnabled}
                      title={capabilitiesImportEnabled ? undefined : importDisabledReason}
                      startIcon={<MaterialSymbol name="delete" size={16} />}
                      onClick={(event) => {
                        stopRowEvent(event);
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
