/** @type {import('tailwindcss').Config} */

module.exports = {
  content: [
    "../../components/**/*.{html, js, svelte, ts}",
    "./stories/**/*.{html,js,svelte,ts}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Poppins", "sans-serif"],
      },
    },
  },
  plugins: [],
};
