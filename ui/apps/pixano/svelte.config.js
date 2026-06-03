import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";
import { pixanoAliases } from "./pixano-aliases.js";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: "../../../src/pixano/api/legacy_dist",
      assets: "../../../src/pixano/api/legacy_dist",
      fallback: "index.html",
    }),
    appDir: "_legacy_app",
    alias: pixanoAliases,
  },
};

export default config;
