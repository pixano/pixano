/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{svelte,js,ts}",
    "../../../ui/components/core/src/**/*.{svelte,js,ts}",
    "../../../ui/components/canvas2d/src/**/*.{svelte,js,ts}",
  ],
  darkMode: "media", // or 'class'
  theme: {
    extend: {
      fontFamily: {
        "DM Sans": ["DM Sans", "sans-serif"],
      },
      colors: {
        main: "#771E5F",
      },
    },
  },
  plugins: [],
};
