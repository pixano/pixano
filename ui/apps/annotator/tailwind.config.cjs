/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{svelte,js,ts}",
    "../../../ui/components/core/src/**/*.{svelte,js,ts}",
    "../../../ui/components/Canvas2D/src/**/*.{svelte,js,ts}",
  ],
  darkMode: "media", // or 'class'
  theme: {},
  plugins: [],
};
