import React from "react";
import { createRoot } from "react-dom/client";
import "@/styles/tokens.css";
import "@/styles/base.css";
import { PlaceholderPage } from "@/pages/PlaceholderPage";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <PlaceholderPage
      title="Viewer (Part 1 Scaffold)"
      subtitle="Routing-compatible page entry is configured for /viewer.html."
    />
  </React.StrictMode>
);
