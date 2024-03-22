module.exports = {
  root: true,
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended-type-checked",
    "plugin:svelte/recommended",
    "prettier",
  ],
  plugins: ["@typescript-eslint"],
  env: {
    es2022: true,
    browser: true,
  },
  parser: "@typescript-eslint/parser",
  parserOptions: {
    tsconfigRootDir: __dirname,
    project: ["./**/tsconfig.json"],
    extraFileExtensions: [".svelte"],
  },
  ignorePatterns: [
    ".eslintrc.cjs",
    ".prettierrc.cjs",
    "svelte.config.js",
    "tailwind.config.cjs",
    "postcss.config.cjs",
    "vite.config.ts",
    // ignore everything in .sveltekit folder
    ".svelte-kit/**/*",
    "mask_utils.ts", // external code
  ],
  overrides: [
    {
      files: ["*.svelte"],
      parser: "svelte-eslint-parser",
      parserOptions: {
        parser: "@typescript-eslint/parser",
      },
    },
  ],
  rules: {
    "@typescript-eslint/no-unsafe-argument": "off", // no types for event.detail in Canvas2D, AnnotationWorkspace and App
    "@typescript-eslint/no-unsafe-member-access": "off", // no types for event.detail.evt in Canvas2D
    "@typescript-eslint/no-misused-promises": [
      "error",
      {
        checksVoidReturn: false,
      },
    ],
  },
};
