import { sveltekit } from "@sveltejs/kit/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

import { pixanoAliases } from "./pixano-aliases.js";

const proxies_list = ["datasets", "io", "inference", "app", "app_models", "media", "views"];

export default defineConfig({
  plugins: [sveltekit(), tailwindcss()],
  resolve: {
    alias: pixanoAliases,
  },
  server: {
    proxy: {
      [`^/(?:${proxies_list.map((s) => `${s}`).join("|")})(?:/|$).*`]: {
        target: "http://127.0.0.1:7492",
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
