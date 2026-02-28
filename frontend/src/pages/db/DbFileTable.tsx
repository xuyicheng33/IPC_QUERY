import React, { KeyboardEvent, MouseEvent, useEffect, useMemo, useState } from "react";
import { CircularProgress } from "@mui/material";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { Select } from "@/components/ui/Select";
import type { DbListItem, DbRowActionState } from "@/lib/types";
import { normalizeDir } from "@/lib/urlState";

type DbFileTableProps = {
  items: DbListItem[];
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
  onBeginDirectoryRename: (path: string) => void;
  onApplyDirectoryRename: (path: string) => void;
  onDeleteDirectory: (path: string) => void;
};

export function DbFileTable({
  items,
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
  onBeginDirectoryRename,
  onApplyDirectoryRename,
  onDeleteDirectory,
}: DbFileTableProps) {
  const [anchorPath, setAnchorPath] = useState("");
  const [activeDirectoryPath, setActiveDirectoryPath] = useState("");
  const orderedFilePaths = useMemo(
    () => items.filter((item) => !item.is_dir).map((item) => normalizeDir(item.relative_path || item.name || "")).filter(Boolean),
    [items]
  );
  const orderedDirectoryPaths = useMemo(
    () => items.filter((item) => item.is_dir).map((item) => normalizeDir(item.relative_path || item.name || "")).filter(Boolean),
    [items]
  );

  useEffect(() => {
    if (!activeDirectoryPath) return;
    if (orderedDirectoryPaths.includes(activeDirectoryPath)) return;
    setActiveDirectoryPath("");
  }, [activeDirectoryPath, orderedDirectoryPaths]);

  const pushOrderedSelection = (next: Set<string>) => {
    onSelectionChange(orderedFilePaths.filter((path) => next.has(path)));
  };

  const applyFileSelection = (rel: string, modifier: { shift: boolean }) => {
    if (!rel) return;
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

    if (next.has(rel)) next.delete(rel);
    else next.add(rel);
    setAnchorPath(rel);
    pushOrderedSelection(next);
  };

  if (items.length === 0) {
    return <EmptyState title="空目录" />;
  }

  const actionWrapClass =
    "pointer-events-none flex items-center justify-end gap-3 text-xs text-muted opacity-0 transition-opacity duration-150 group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100";
  const actionTextClass =
    "whitespace-nowrap bg-transparent p-0 text-xs text-muted hover:text-accent focus-visible:outline-none focus-visible:text-accent disabled:cursor-not-allowed disabled:text-muted/60";
  const actionSplitClass = "text-border";

  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface">
      <div role="list" aria-label="数据库文件列表">
        {items.map((item) => {
          const rel = normalizeDir(item.relative_path || item.name || "");
          const actionState = getRowActionState(rel);
          const moveTarget = normalizeDir(actionState.value || "");
          const previewHref = `/pdf/${encodeURIComponent(rel)}#page=1`;
          const pending = actionState.phase === "pending";
          const isDirectory = item.is_dir;
          const isSelected = !isDirectory && selectedPaths.has(rel);
          const isActiveDirectory = isDirectory && activeDirectoryPath === rel;
          const displayName = String(item.name || rel || "-");
          const showRelativePath = Boolean(rel && rel !== displayName);
          const actionAreaClass = "w-[180px] md:w-[332px]";

          const stopRowEvent = (event: MouseEvent<HTMLElement>) => {
            event.preventDefault();
            event.stopPropagation();
          };

          const stopRowKeyEvent = (event: KeyboardEvent<HTMLElement>) => {
            event.preventDefault();
            event.stopPropagation();
          };

          return (
            <div
              key={rel || item.name}
              role={isDirectory ? "button" : "listitem"}
              aria-label={
                isDirectory ? `目录 ${displayName}${isActiveDirectory ? "（已选）" : ""}` : `${displayName}${isSelected ? "（已选）" : ""}`
              }
              tabIndex={isDirectory ? 0 : -1}
              className={`group grid grid-cols-[36px_28px_minmax(0,1fr)_180px] items-center gap-2 border-b border-border px-3 py-2 last:border-b-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent md:grid-cols-[36px_28px_minmax(0,1fr)_332px] ${
                isSelected || isActiveDirectory ? "bg-accent-soft" : "hover:bg-surface-soft"
              }`}
              onClick={(event) => {
                if (isDirectory) {
                  event.preventDefault();
                  setActiveDirectoryPath(rel);
                }
              }}
              onKeyDown={(event) => {
                if (isDirectory) {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    onOpenDirectory(rel);
                  } else if (event.key === " ") {
                    event.preventDefault();
                    setActiveDirectoryPath(rel);
                  }
                  return;
                }
              }}
            >
              <div className="flex w-9 items-center justify-center">
                {isDirectory ? (
                  <span className="h-4 w-4" />
                ) : (
                  <input
                    type="checkbox"
                    checked={isSelected}
                    aria-label={`${displayName}${isSelected ? "已选中" : "未选中"}`}
                    className="h-4 w-4"
                    style={{ accentColor: "var(--color-accent)" }}
                    onClick={(event) => {
                      event.preventDefault();
                      stopRowEvent(event);
                      if (actionState.mode !== "normal") return;
                      applyFileSelection(rel, {
                        shift: event.shiftKey,
                      });
                    }}
                    onChange={() => undefined}
                  />
                )}
              </div>

              <div className="flex w-7 items-center justify-center">
                <MaterialSymbol name={isDirectory ? "folder" : "description"} size={20} className={isDirectory ? "text-accent" : "text-muted"} />
              </div>

              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-text">{displayName}</div>
                {showRelativePath ? <div className="truncate font-mono text-xs text-muted">{rel}</div> : null}
              </div>

              <div className={actionAreaClass}>
                {isDirectory ? (
                  actionState.mode === "renaming" ? (
                    <div className="grid w-full gap-1">
                      <div className="flex items-center gap-1">
                        <Input
                          name={`rename-dir-${rel}`}
                          value={actionState.value}
                          onChange={(event) =>
                            onSetRowActionState(rel, { ...actionState, value: event.target.value, error: "", phase: "idle" })
                          }
                          onFocus={(event) => {
                            event.target.select();
                          }}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") {
                              stopRowKeyEvent(event);
                              onApplyDirectoryRename(rel);
                            } else if (event.key === "Escape") {
                              stopRowKeyEvent(event);
                              onClearRowActionState(rel);
                            }
                          }}
                          className="h-8"
                          placeholder="新目录名"
                          disabled={pending}
                          autoFocus
                        />
                        <button
                          type="button"
                          className={actionTextClass}
                          onClick={(event) => {
                            stopRowEvent(event);
                            onApplyDirectoryRename(rel);
                          }}
                          disabled={pending}
                          aria-label={pending ? "正在改名" : "确认改名"}
                          title={pending ? "正在改名" : "确认改名"}
                        >
                          {pending ? (
                            <span className="inline-flex items-center gap-1">
                              <CircularProgress size={12} />
                              处理中
                            </span>
                          ) : (
                            "确认"
                          )}
                        </button>
                        <button
                          type="button"
                          className={actionTextClass}
                          onClick={(event) => {
                            stopRowEvent(event);
                            onClearRowActionState(rel);
                          }}
                          disabled={pending}
                          aria-label="取消改名"
                          title="取消改名"
                        >
                          取消
                        </button>
                      </div>
                      {actionState.error ? <div className="text-xs text-danger">{actionState.error}</div> : null}
                    </div>
                  ) : (
                    <div className={actionWrapClass}>
                      <button
                        type="button"
                        className={actionTextClass}
                        disabled={!rel}
                        onClick={(event) => {
                          stopRowEvent(event);
                          if (!rel) return;
                          onOpenDirectory(rel);
                        }}
                      >
                        进入
                      </button>
                      <span className={actionSplitClass}>|</span>
                      <button
                        type="button"
                        className={actionTextClass}
                        disabled={!rel || !capabilitiesImportEnabled}
                        title={capabilitiesImportEnabled ? undefined : importDisabledReason}
                        onClick={(event) => {
                          stopRowEvent(event);
                          onBeginDirectoryRename(rel);
                        }}
                      >
                        改名
                      </button>
                      <span className={actionSplitClass}>|</span>
                      <button
                        type="button"
                        className={actionTextClass}
                        disabled={!rel || !capabilitiesImportEnabled}
                        title={capabilitiesImportEnabled ? undefined : importDisabledReason}
                        onClick={(event) => {
                          stopRowEvent(event);
                          onDeleteDirectory(rel);
                        }}
                      >
                        删除
                      </button>
                    </div>
                )) : actionState.mode === "renaming" ? (
                  <div className="grid w-full gap-1">
                    <div className="flex items-center gap-1">
                      <Input
                        name={`rename-${rel}`}
                        value={actionState.value}
                        onChange={(event) =>
                          onSetRowActionState(rel, { ...actionState, value: event.target.value, error: "", phase: "idle" })
                        }
                        onFocus={(event) => {
                          event.target.select();
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            stopRowKeyEvent(event);
                            onApplyRename(rel);
                          } else if (event.key === "Escape") {
                            stopRowKeyEvent(event);
                            onClearRowActionState(rel);
                          }
                        }}
                        className="h-8"
                        placeholder="新文件名，如 b.pdf"
                        disabled={pending}
                        autoFocus
                      />
                      <button
                        type="button"
                        className={actionTextClass}
                        onClick={(event) => {
                          stopRowEvent(event);
                          onApplyRename(rel);
                        }}
                        disabled={pending}
                        aria-label={pending ? "正在改名" : "确认改名"}
                        title={pending ? "正在改名" : "确认改名"}
                      >
                        {pending ? (
                          <span className="inline-flex items-center gap-1">
                            <CircularProgress size={12} />
                            处理中
                          </span>
                        ) : (
                          "确认"
                        )}
                      </button>
                      <button
                        type="button"
                        className={actionTextClass}
                        onClick={(event) => {
                          stopRowEvent(event);
                          onClearRowActionState(rel);
                        }}
                        disabled={pending}
                        aria-label="取消改名"
                        title="取消改名"
                      >
                        取消
                      </button>
                    </div>
                    {actionState.error ? <div className="text-xs text-danger">{actionState.error}</div> : null}
                  </div>
                ) : actionState.mode === "moving" ? (
                  <div className="grid w-full gap-1">
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
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            stopRowKeyEvent(event);
                            onApplyMove(rel);
                          } else if (event.key === "Escape") {
                            stopRowKeyEvent(event);
                            onClearRowActionState(rel);
                          }
                        }}
                        disabled={pending}
                        autoFocus
                      >
                        {knownDirectories.map((dir) => (
                          <option key={dir || "root"} value={dir}>
                            {dir || "/"}
                          </option>
                        ))}
                      </Select>
                      <button
                        type="button"
                        className={actionTextClass}
                        onClick={(event) => {
                          stopRowEvent(event);
                          onApplyMove(rel);
                        }}
                        disabled={pending}
                        aria-label={pending ? "正在移动" : "确认移动"}
                        title={pending ? "正在移动" : "确认移动"}
                      >
                        {pending ? (
                          <span className="inline-flex items-center gap-1">
                            <CircularProgress size={12} />
                            处理中
                          </span>
                        ) : (
                          "确认"
                        )}
                      </button>
                      <button
                        type="button"
                        className={actionTextClass}
                        onClick={(event) => {
                          stopRowEvent(event);
                          onClearRowActionState(rel);
                        }}
                        disabled={pending}
                        aria-label="取消移动"
                        title="取消移动"
                      >
                        取消
                      </button>
                    </div>
                    {actionState.error ? <div className="text-xs text-danger">{actionState.error}</div> : null}
                  </div>
                ) : (
                  <div className={actionWrapClass}>
                    <button
                      type="button"
                      className={actionTextClass}
                      disabled={!rel}
                      onClick={(event) => {
                        stopRowEvent(event);
                        if (!rel) return;
                        window.open(previewHref, "_blank", "noopener,noreferrer");
                      }}
                    >
                      预览
                    </button>
                    <span className={actionSplitClass}>|</span>
                    <button
                      type="button"
                      className={actionTextClass}
                      disabled={!rel || !capabilitiesImportEnabled}
                      title={capabilitiesImportEnabled ? undefined : importDisabledReason}
                      onClick={(event) => {
                        stopRowEvent(event);
                        onBeginRename(rel);
                      }}
                    >
                      改名
                    </button>
                    <span className={actionSplitClass}>|</span>
                    <button
                      type="button"
                      className={actionTextClass}
                      disabled={!rel || !capabilitiesImportEnabled}
                      title={capabilitiesImportEnabled ? undefined : importDisabledReason}
                      onClick={(event) => {
                        stopRowEvent(event);
                        onBeginMove(rel);
                      }}
                    >
                      移动
                    </button>
                    <span className={actionSplitClass}>|</span>
                    <button
                      type="button"
                      className={actionTextClass}
                      disabled={!rel || !capabilitiesImportEnabled}
                      title={capabilitiesImportEnabled ? undefined : importDisabledReason}
                      onClick={(event) => {
                        stopRowEvent(event);
                        onDeleteSingle(rel);
                      }}
                    >
                      删除
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
