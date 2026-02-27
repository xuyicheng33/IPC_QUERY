import React from "react";
import { Box, CircularProgress, Typography } from "@mui/material";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { Select } from "@/components/ui/Select";
import { Table, TableWrap, TD, TH } from "@/components/ui/Table";
import type { DbRowActionState, DocsTreeFile, JobStatus } from "@/lib/types";
import { normalizeDir } from "@/lib/urlState";

type DbFileTableProps = {
  files: DocsTreeFile[];
  selectedPaths: Set<string>;
  selectAllChecked: boolean;
  knownDirectories: string[];
  jobStatusByPath: Map<string, JobStatus>;
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
};

export function DbFileTable({
  files,
  selectedPaths,
  selectAllChecked,
  knownDirectories,
  jobStatusByPath,
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
}: DbFileTableProps) {
  if (files.length === 0) {
    return <EmptyState title="无 PDF 文件" />;
  }

  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <TH className="w-[48px]">
              <input
                type="checkbox"
                aria-label="全选文件"
                checked={selectAllChecked}
                onChange={(event) => onToggleSelectAll(event.target.checked)}
              />
            </TH>
            <TH>文件名</TH>
            <TH>入库状态</TH>
            <TH>任务状态</TH>
            <TH>操作</TH>
          </tr>
        </thead>
        <tbody>
          {files.map((file) => {
            const rel = normalizeDir(file.relative_path || file.name || "");
            const indexed = Boolean(file.indexed);
            const taskStatus = jobStatusByPath.get(rel) || "queued";
            const checked = selectedPaths.has(rel);
            const actionState = getRowActionState(rel);
            const moveTarget = normalizeDir(actionState.value || "");
            const previewHref = `/viewer.html?pdf=${encodeURIComponent(rel)}&page=1`;
            const pending = actionState.phase === "pending";

            return (
              <tr key={rel || file.name} className="group">
                <TD>
                  <input type="checkbox" checked={checked} disabled={!rel} onChange={() => onToggleSelect(rel)} />
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
                <TD className="min-w-[360px]">
                  {actionState.mode === "renaming" ? (
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
                    <Box display="flex" alignItems="center" gap={0.5} className="opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100">
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
                        onClick={() => onDeleteSingle(rel)}
                      >
                        删除
                      </Button>
                    </Box>
                  )}
                </TD>
              </tr>
            );
          })}
        </tbody>
      </Table>
      <Typography variant="caption" color="text.secondary" sx={{ px: 2, py: 1, display: "block" }}>
        行操作状态机：idle → pending → success/error
      </Typography>
    </TableWrap>
  );
}
