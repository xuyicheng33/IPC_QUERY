import React from "react";
import { createRoot } from "react-dom/client";
import "@/styles/tokens.css";
import "@/styles/base.css";
import { PartDetailPage } from "@/pages/PartDetailPage";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <PartDetailPage />
  </React.StrictMode>
);
