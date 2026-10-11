import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Served by FastAPI under /next while screens move over from the legacy app.
// `npm run dev` proxies the API and the shared /static files (tokens, fonts,
// theme-boot.js) to a local Curiculy on port 3040.
export default defineConfig({
  base: "/next/",
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://localhost:3040",
      "/static": "http://localhost:3040",
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
