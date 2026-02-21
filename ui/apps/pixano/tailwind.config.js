import { theme } from "./src/lib/ui/tailwindTheme.js";

export default {
  content: [
    "./src/app.html",
    "./src/routes/**/*.{svelte,js,ts,jsx,tsx}",
    "./src/components/**/*.{svelte,js,ts,jsx,tsx}",
    "./src/lib/ui/core/**/*.{js,ts}",
  ],
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
