import React from "react";
import { AppBar, Box, Container, Stack, Toolbar, Typography } from "@mui/material";
import { Button } from "@/components/ui/Button";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";

type ShellAction = {
  href: string;
  label: string;
  icon?: React.ReactNode;
};

type AppShellProps = {
  title?: string;
  actions?: ShellAction[];
  showBack?: boolean;
  backHref?: string;
  backLabel?: string;
  children: React.ReactNode;
  contentClassName?: string;
};

export function AppShell({
  title = "IPC 查询系统",
  actions,
  showBack = true,
  backHref = "/",
  backLabel = "返回上一级",
  children,
  contentClassName,
}: AppShellProps) {
  const nav =
    actions && actions.length > 0
      ? actions
      : [
        { href: "/search", label: "搜索", icon: <MaterialSymbol name="search" size={18} /> },
        { href: "/db", label: "数据库", icon: <MaterialSymbol name="database" size={18} /> },
      ];

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default", color: "text.primary" }}>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: "1px solid", borderColor: "divider" }}>
        <Toolbar sx={{ px: { xs: 2, md: 3 }, py: 1 }}>
          <Container maxWidth={false} sx={{ maxWidth: 1360, px: "0 !important" }}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }} justifyContent="space-between">
              <a href="/">
                <Typography variant="h6">{title}</Typography>
              </a>
              <Stack component="nav" direction="row" spacing={1} flexWrap="wrap" aria-label="主导航">
                {showBack ? (
                  <Button
                    variant="ghost"
                    startIcon={<MaterialSymbol name="arrow_back" size={18} />}
                    onClick={() => {
                      if (window.history.length > 1) {
                        window.history.back();
                        return;
                      }
                      window.location.href = backHref;
                    }}
                  >
                    {backLabel}
                  </Button>
                ) : null}
                {nav.map((item) => (
                  <a key={item.href} href={item.href}>
                    <Button variant="ghost" startIcon={item.icon}>
                      {item.label}
                    </Button>
                  </a>
                ))}
              </Stack>
            </Stack>
          </Container>
        </Toolbar>
      </AppBar>
      <Container maxWidth={false} sx={{ maxWidth: 1360, px: { xs: 2, md: 3 }, py: 3 }} className={contentClassName}>
        {children}
      </Container>
    </Box>
  );
}
