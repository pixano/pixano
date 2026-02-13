import { theme } from "@pixano/core/theme/tailwindTheme";

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: {
    relative: true,
    files: [
      "./.storybook/preview-head.html",
      "./stories/**/*.{html,js,svelte,ts}",
      "./src/routes/**/*.{svelte,js,ts,jsx,tsx}",
      "./src/components/**/*.{svelte,js,ts,jsx,tsx}",
      "../../components/core/src/**/*.{svelte,js,ts,jsx,tsx}",
      "../../components/datasetItemWorkspace/src/**/*.{svelte,js,ts,jsx,tsx}",
      "../../components/canvas2d/src/**/*.{svelte,js,ts,jsx,tsx}",
      "../../components/canvas3d/src/**/*.{svelte,js,ts,jsx,tsx}",
      "../../components/table/src/**/*.{svelte,js,ts,jsx,tsx}",
    ],
  },
  darkMode: "class",
  safelist: ["bg-primary", "text-3xl", "lg:text-4xl"],
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
