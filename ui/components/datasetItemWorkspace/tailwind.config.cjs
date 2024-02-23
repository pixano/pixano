import { theme } from "@pixano/core/theme/tailwindTheme";

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{svelte,js,ts}",
    "../canvas2d/src/**/*.{svelte,js,ts}",
    "../canvas3d/src/**/*.{svelte,js,ts}",
    "../core/src/**/*.{svelte,js,ts}",
    "../../apps/annotator/src/.{svelte,js,ts}",
  ],
  darkMode: "media", // or 'class'
  theme: {
    extend: {
      ...theme,
      colors: {
        ...theme.colors,
      },
    },
  },
  plugins: [],
};
