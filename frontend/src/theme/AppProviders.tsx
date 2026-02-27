import React from "react";
import { CssBaseline, GlobalStyles, ThemeProvider } from "@mui/material";
import { md3Theme } from "@/theme/md3Theme";

type AppProvidersProps = {
  children: React.ReactNode;
};

export function AppProviders({ children }: AppProvidersProps) {
  return (
    <ThemeProvider theme={md3Theme}>
      <CssBaseline />
      <GlobalStyles
        styles={{
          ".material-symbols-rounded": {
            fontFamily: '"Material Symbols Rounded"',
            fontWeight: "normal",
            fontStyle: "normal",
            fontSize: "1.2rem",
            lineHeight: 1,
            letterSpacing: "normal",
            textTransform: "none",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            whiteSpace: "nowrap",
            direction: "ltr",
            fontVariationSettings: "'FILL' 0, 'wght' 500, 'GRAD' 0, 'opsz' 24",
          },
        }}
      />
      {children}
    </ThemeProvider>
  );
}
