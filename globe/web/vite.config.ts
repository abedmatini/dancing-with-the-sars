import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type PluginOption } from "vite";
import cesium from "vite-plugin-cesium";

const cesiumPlugin = cesium as unknown as (options?: object) => PluginOption;

export default defineConfig({
  plugins: [react(), tailwindcss(), cesiumPlugin()],
  server: {
    host: "0.0.0.0",
    port: 4178,
  },
  preview: {
    host: "0.0.0.0",
    port: 4178,
  },
});
