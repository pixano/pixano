import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import { pixanoAliases } from "./pixano-aliases.js";

const proxies_list = [
  "datasets",
  "browser",
  "thumbnail",
  "dataset_items",
  "items",
  "items_info",
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
  resolve: {
    alias: pixanoAliases,
  },
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
