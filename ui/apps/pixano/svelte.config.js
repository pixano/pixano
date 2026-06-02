import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";
import { pixanoAliases } from "./pixano-aliases.js";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: "../../../src/pixano/api/classic_dist",
      assets: "../../../src/pixano/api/classic_dist",
      fallback: "index.html",
    }),
    appDir: "_classic_app",
    alias: pixanoAliases,
  },
};

export default config;
