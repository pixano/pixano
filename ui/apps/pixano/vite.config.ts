import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

const proxies_list = [
  "datasets",
  "browser",
  "dataset_items",
  "items",
  "views",
  "entities",
  "annotations",
  "embeddings",
  "sources",
  "media",
  "app_models",
  "models",
  "inference",
];

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    proxy: {
      [`^/(?:${proxies_list.map((s) => `${s}`).join("|")})(?:/|$).*`]: {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
