import { theme } from "@pixano/core/theme/tailwindTheme";

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{svelte,js,ts}"],
  darkMode: "class",
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
