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
    // TODO: Refactor code and remove rules if possible
    "no-undef": "off",
    "@typescript-eslint/no-unsafe-member-access": "off",
    "@typescript-eslint/no-unsafe-assignment": "off",
    "@typescript-eslint/no-unsafe-call": "off",
    "@typescript-eslint/no-base-to-string": "off", // can't add type annotations in Svelte Code for variables like DatasetItemFeature.value
    "@typescript-eslint/no-unsafe-argument": "off", // can't add type annotations in Svelte code for variables like event.detail
  },
};
