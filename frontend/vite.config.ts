import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  worker: { format: "es" }, // MapLibre's worker is an ES module
  // MapLibre 6 locates its web worker relative to its own module URL; pre-bundling breaks that.
  optimizeDeps: { exclude: ["maplibre-gl"] },
  build: {
    // MapLibre + deck.gl are ~520 kB gzipped by themselves; that chunk is lazy-loaded.
    chunkSizeWarningLimit: 2000,
    rollupOptions: {
      output: {
        // Map libraries are large and change rarely: keep them in their own cacheable chunk.
        manualChunks: (id) =>
          /node_modules\/(maplibre-gl|@deck\.gl|@luma\.gl|@loaders\.gl|@math\.gl)\//.test(id)
            ? "map"
            : undefined,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
