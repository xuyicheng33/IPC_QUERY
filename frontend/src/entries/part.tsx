import React from "react";
import { createRoot } from "react-dom/client";
import "@/styles/tokens.css";
import "@/styles/base.css";
import { PartDetailPage } from "@/pages/PartDetailPage";
import { AppProviders } from "@/theme/AppProviders";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProviders>
      <PartDetailPage />
    </AppProviders>
  </React.StrictMode>
);
