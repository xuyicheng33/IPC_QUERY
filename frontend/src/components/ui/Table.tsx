import React from "react";
import {
  Table as MuiTable,
  TableCell,
  TableContainer,
  type TableContainerProps,
  type TableProps as MuiTableProps,
  type TableCellProps,
} from "@mui/material";
import { cn } from "@/lib/cn";

export function TableWrap({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <TableContainer component="div" className={className as TableContainerProps["className"]} sx={{ borderRadius: 3 }}>
      {children}
    </TableContainer>
  );
}

export function Table({ className, children }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <MuiTable size="small" className={className as MuiTableProps["className"]}>
      {children}
    </MuiTable>
  );
}

export function TH({ className, children }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <TableCell
      className={className as TableCellProps["className"]}
      sx={{
        py: 1.2,
        px: 1.5,
        bgcolor: "action.hover",
        borderBottomColor: "divider",
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: 0.4,
      }}
    >
      {children}
    </TableCell>
  );
}

export function TD({ className, children }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <TableCell className={cn("align-top", className)} sx={{ py: 1.2, px: 1.5, borderBottomColor: "divider" }}>
      {children}
    </TableCell>
  );
}
