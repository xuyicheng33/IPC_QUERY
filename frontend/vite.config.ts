import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../web"),
    emptyOutDir: false,
    sourcemap: false,
    rollupOptions: {
      input: {
        index: path.resolve(__dirname, "index.html"),
        search: path.resolve(__dirname, "search.html"),
        part: path.resolve(__dirname, "part.html"),
        db: path.resolve(__dirname, "db.html"),
      },
      output: {
        entryFileNames: "assets/[name].js",
        chunkFileNames: "assets/chunks/[name].js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith(".css")) {
            return "assets/[name].css";
          }
          return "assets/[name][extname]";
        },
      },
    },
  },
});
