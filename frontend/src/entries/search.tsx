import React from "react";
import { createRoot } from "react-dom/client";
import "@/styles/tokens.css";
import "@/styles/base.css";
import { SearchPage } from "@/pages/SearchPage";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SearchPage />
  </React.StrictMode>
);
