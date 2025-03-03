import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

const proxies_list = [
  "/datasets",
  "/browser",
  "/dataset_items",
  "/items",
  "/views",
  "/entities",
  "/annotations",
  "/embeddings",
  "/sources",
  "/media",
  "/models",
  "/app_models",
  "/inference",
];
const proxy_conf = { target: "http://127.0.0.1:8000", changeOrigin: true, secure: false };
const proxies = Object.fromEntries(proxies_list.map((proxy) => [proxy, { ...proxy_conf }]));

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    proxy: proxies,
  },
});
