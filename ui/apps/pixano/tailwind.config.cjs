import { theme } from "@pixano/core/theme/tailwindTheme";

export default {
  content: [
    "./src/app.html",
    "./src/routes/**/*.{svelte,js,ts,jsx,tsx}",
    "./src/components/**/*.{svelte,js,ts,jsx,tsx}",
    "../../components/core/src/**/*.{svelte,js,ts,jsx,tsx}",
    "../../components/imageWorkspace/src/**/*.{svelte,js,ts,jsx,tsx}",
    "../../components/canvas2d/src/**/*.{svelte,js,ts,jsx,tsx}",
  ],
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
