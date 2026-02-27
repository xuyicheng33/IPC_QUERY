import React from "react";
import { createRoot } from "react-dom/client";
import "@/styles/tokens.css";
import "@/styles/base.css";
import { PlaceholderPage } from "@/pages/PlaceholderPage";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <PlaceholderPage
      title="Home (Part 1 Scaffold)"
      subtitle="React multi-entry scaffold is ready. UI implementation starts from Part 2."
    />
  </React.StrictMode>
);
