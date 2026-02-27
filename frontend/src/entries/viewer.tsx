import React from "react";
import { createRoot } from "react-dom/client";
import "@/styles/tokens.css";
import "@/styles/base.css";
import { ViewerPage } from "@/pages/ViewerPage";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ViewerPage />
  </React.StrictMode>
);
