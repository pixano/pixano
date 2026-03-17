// @ts-check
import { defineConfig } from "astro/config";
import svelte from "@astrojs/svelte";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";
import expressiveCode from "astro-expressive-code";

export default defineConfig({
  site: "https://pixano.github.io",
  base: "/pixano",
  integrations: [
    expressiveCode({
      themes: ["github-dark", "github-light"],
      themeCssSelector: (theme) => {
        if (theme.name === "github-dark") return '[data-theme="dark"]';
        return '[data-theme="light"]';
      },
      styleOverrides: {
        borderRadius: "0.75rem",
        borderColor: "var(--px-border)",
        codeFontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        codeFontSize: "0.875rem",
        codeLineHeight: "1.7",
        uiFontFamily: "'Inter', system-ui, sans-serif",
      },
      frames: {
        showCopyToClipboardButton: true,
      },
    }),
    mdx(),
    svelte(),
    sitemap(),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
  markdown: {
    remarkPlugins: [],
    rehypePlugins: [],
  },
  redirects: {
    "/": "/pixano/getting_started/",
  },
});
