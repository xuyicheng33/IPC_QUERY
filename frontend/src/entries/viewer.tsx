import React from "react";
import { createRoot } from "react-dom/client";
import "@/styles/tokens.css";
import "@/styles/base.css";
import { ViewerPage } from "@/pages/ViewerPage";
import { AppProviders } from "@/theme/AppProviders";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProviders>
      <ViewerPage />
    </AppProviders>
  </React.StrictMode>
);
