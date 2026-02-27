import { alpha, createTheme } from "@mui/material/styles";

export const md3Theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#00639B",
      light: "#3E7DB5",
      dark: "#004A75",
      contrastText: "#FFFFFF",
    },
    secondary: {
      main: "#4A626E",
      light: "#657B86",
      dark: "#324852",
      contrastText: "#FFFFFF",
    },
    error: {
      main: "#BA1A1A",
    },
    background: {
      default: "#F7F9FC",
      paper: "#FFFFFF",
    },
    text: {
      primary: "#162027",
      secondary: "#4C5B66",
    },
    divider: "#D7E2E9",
  },
  shape: {
    borderRadius: 12,
  },
  typography: {
    fontFamily: '"Roboto", "Noto Sans SC", "PingFang SC", "Segoe UI", system-ui, sans-serif',
    h5: {
      fontWeight: 600,
      letterSpacing: 0.15,
    },
    h6: {
      fontWeight: 600,
      letterSpacing: 0.1,
    },
    button: {
      textTransform: "none",
      fontWeight: 600,
      letterSpacing: 0.1,
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: "#F7F9FC",
          color: "#162027",
        },
      },
    },
    MuiPaper: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: ({ theme }) => ({
          border: `1px solid ${theme.palette.divider}`,
        }),
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 20,
          minHeight: 40,
          paddingInline: 16,
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        size: "small",
      },
    },
    MuiInputBase: {
      styleOverrides: {
        root: ({ theme }) => ({
          borderRadius: theme.shape.borderRadius,
        }),
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: ({ theme }) => ({
          transition: "background-color 180ms ease-out",
          "&:hover": {
            backgroundColor: alpha(theme.palette.primary.main, 0.06),
          },
        }),
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
        },
      },
    },
  },
});
