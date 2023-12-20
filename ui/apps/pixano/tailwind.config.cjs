import { theme } from "@pixano/core/theme/tailwindTheme";

export default {
  content: [
    "./src/app.html",
    "./src/routes/**/*.{svelte,js,ts,jsx,tsx}",
    "./src/components/**/*.{svelte,js,ts,jsx,tsx}",
    "../../components/core/src/**/*.{svelte,js,ts,jsx,tsx}",
    "../../components/imageWorkspace/src/**/*.{svelte,js,ts,jsx,tsx}",
  ],
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
