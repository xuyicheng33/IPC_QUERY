import React from "react";
import { Box, Typography } from "@mui/material";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import type { DocsTreeResponse } from "@/lib/types";
import { normalizeDir } from "@/lib/urlState";

type DbDirectoryTreePanelProps = {
  currentPath: string;
  treeCache: Map<string, DocsTreeResponse>;
  expandedDirs: Set<string>;
  onRefresh: () => void;
  onLoadDirectory: (path: string) => void;
  onToggleExpand: (path: string, expanded: boolean) => void;
  onEnsureTreeNode: (path: string) => Promise<void>;
};

export function DbDirectoryTreePanel({
  currentPath,
  treeCache,
  expandedDirs,
  onRefresh,
  onLoadDirectory,
  onToggleExpand,
  onEnsureTreeNode,
}: DbDirectoryTreePanelProps) {
  const renderTree = (path: string, depth: number): React.ReactNode => {
    const node = treeCache.get(path);
    if (!node) return null;

    return (node.directories || []).map((dir) => {
      const dirPath = normalizeDir(dir.path || "");
      const expanded = expandedDirs.has(dirPath);
      return (
        <Box key={`dir-${dirPath}`} display="flex" flexDirection="column">
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 0.5,
              borderRadius: 2,
              px: 0.5,
              py: 0.5,
              pl: `${depth * 14}px`,
              bgcolor: dirPath === currentPath ? "action.selected" : "transparent",
              "&:hover": { bgcolor: "action.hover" },
            }}
          >
            <button
              type="button"
              className="inline-flex h-6 w-6 items-center justify-center rounded border border-border bg-surface hover:bg-surface-soft"
              onClick={async () => {
                if (expanded) {
                  onToggleExpand(dirPath, false);
                  return;
                }
                onToggleExpand(dirPath, true);
                await onEnsureTreeNode(dirPath);
              }}
              aria-label={expanded ? "收起目录" : "展开目录"}
            >
              <MaterialSymbol name={expanded ? "expand_more" : "chevron_right"} size={16} />
            </button>
            <button
              type="button"
              className="flex flex-1 items-center gap-1.5 rounded px-1 py-1 text-left font-mono text-xs hover:bg-surface"
              onClick={() => onLoadDirectory(dirPath)}
            >
              <MaterialSymbol name="folder" size={16} sx={{ color: "text.secondary" }} />
              {dir.name || dirPath || "-"}
            </button>
          </Box>

          {expanded ? (
            <>
              {(treeCache.get(dirPath)?.files || []).map((file) => (
                <Box
                  key={`file-${file.relative_path}`}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 0.5,
                    py: 0.5,
                    pl: `${(depth + 1) * 14}px`,
                    fontSize: 12,
                    color: "text.secondary",
                  }}
                >
                  <MaterialSymbol name="description" size={16} />
                  <span className="font-mono">{file.relative_path || file.name || "-"}</span>
                </Box>
              ))}
              {renderTree(dirPath, depth + 1)}
            </>
          ) : null}
        </Box>
      );
    });
  };

  return (
    <Card className="grid gap-3">
      <Box display="flex" alignItems="center" justifyContent="space-between">
        <Typography variant="body2" fontWeight={600}>
          目录树
        </Typography>
        <Button variant="ghost" className="h-9 gap-2 px-3" onClick={onRefresh} startIcon={<MaterialSymbol name="refresh" size={16} />}>
          刷新树
        </Button>
      </Box>

      <Box className="min-h-[500px] rounded-md border border-border bg-surface p-2">
        <div className={`mb-1 flex items-center rounded-md px-1 py-1 ${currentPath === "" ? "bg-accent-soft" : ""}`}>
          <button
            type="button"
            className="flex flex-1 items-center gap-1.5 rounded px-1 py-1 text-left font-mono text-xs hover:bg-surface-soft"
            onClick={() => onLoadDirectory("")}
          >
            <MaterialSymbol name="folder" size={16} sx={{ color: "text.secondary" }} />/
          </button>
        </div>

        {(treeCache.get("")?.files || []).map((file) => (
          <div key={`root-file-${file.relative_path}`} className="flex items-center gap-1.5 py-1 pl-4 text-xs text-muted">
            <MaterialSymbol name="description" size={16} />
            <span className="font-mono">{file.relative_path || file.name || "-"}</span>
          </div>
        ))}

        {renderTree("", 1)}
      </Box>
    </Card>
  );
}
