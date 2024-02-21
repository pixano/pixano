import { theme } from "@pixano/core/theme/tailwindTheme";

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: {
    relative: true,
    files: [
      "../../components/**/*.{html, js, svelte, ts}",
      "./stories/**/*.{html,js,svelte,ts}",
      "../../components/core/src/**/*.svelte",
    ],
  },
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
