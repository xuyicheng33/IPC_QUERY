import React from "react";
import { createRoot } from "react-dom/client";
import "@/styles/tokens.css";
import "@/styles/base.css";
import { DbPage } from "@/pages/DbPage";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <DbPage />
  </React.StrictMode>
);
