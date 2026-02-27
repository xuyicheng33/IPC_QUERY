import React from "react";
import { createRoot } from "react-dom/client";
import "@/styles/tokens.css";
import "@/styles/base.css";
import { HomePage } from "@/pages/HomePage";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <HomePage />
  </React.StrictMode>
);
