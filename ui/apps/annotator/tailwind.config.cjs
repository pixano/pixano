import { theme } from "@pixano/core/theme/tailwindTheme";

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{svelte,js,ts}",
    "../../../ui/components/core/src/**/*.{svelte,js,ts}",
    "../../../ui/components/canvas2d/src/**/*.{svelte,js,ts}",
    "../../components/imageWorkspace/src/**/*.{svelte,js,ts}",
  ],
  darkMode: "media", // or 'class'
  theme: {
    extend: {
      ...theme,
      colors: {
        main: "#771E5F",
        secondary: "#872f6e",
        ...theme.colors,
      },
    },
  },
  plugins: [],
};
