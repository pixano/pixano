import { theme } from "@pixano/core/theme/tailwindTheme";

export default {
  content: [
    "./src/app.html",
    "./src/routes/**/*.{svelte,js,ts,jsx,tsx}",
    "./src/components/**/*.{svelte,js,ts,jsx,tsx}",
    "../../components/core/src/**/*.{svelte,js,ts,jsx,tsx}",
    "../../components/datasetItemWorkspace/src/**/*.{svelte,js,ts,jsx,tsx}",
    "../../components/canvas2d/src/**/*.{svelte,js,ts,jsx,tsx}",
    "../../components/canvas3d/src/**/*.{svelte,js,ts,jsx,tsx}",
    "../../components/table/src/**/*.{svelte,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      ...theme,
      colors: {
        ...theme.colors,
      },
    },
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: [
      {
        pixano: {
          ...require("daisyui/src/theming/themes")["light"],
          fontFamily: "Montserrat",
          primary: "#771E5F",
          info: "#64748b"
        },
      },
    ], // false: only light + dark | true: all themes | array: specific themes like this ["light", "dark", "cupcake"]
    darkTheme: "dark", // name of one of the included themes for dark mode
    base: true, // applies background color and foreground color for root element by default
    styled: true, // include daisyUI colors and design decisions for all components
    utils: true, // adds responsive and modifier utility classes
    prefix: "", // prefix for daisyUI classnames (components, modifiers and responsive class names. Not colors)
    logs: true, // Shows info about daisyUI version and used config in the console when building your CSS
    themeRoot: ":root", // The element that receives theme color CSS variables
  },
};
