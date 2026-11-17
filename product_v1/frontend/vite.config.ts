import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "SCREENSHOTLEGAL_");
  return {
    plugins: [react()],
    build: { rollupOptions: { input: { workbench: "index.html", console: "console.html", evaluation: "evaluation.html", studio: "studio.html", review: "review.html" } } },
    server: {
      host: "0.0.0.0",
      allowedHosts: (process.env.SCREENSHOTLEGAL_ALLOWED_HOSTS || env.SCREENSHOTLEGAL_ALLOWED_HOSTS || "").split(",").map(host => host.trim()).filter(Boolean),
      proxy: { "/v1": process.env.SCREENSHOTLEGAL_API_URL || "http://127.0.0.1:18430" },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test-setup.ts"],
      exclude: ["e2e/**", "node_modules/**"],
    },
  };
});
