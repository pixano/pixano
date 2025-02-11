module.exports = {
  useTabs: false,
  singleQuote: false,
  trailingComma: "all",
  printWidth: 100,
  importOrder: ["<THIRD_PARTY_MODULES>", "", "^(@pixano)(/.*)$", "", "^([$]app|[$]lib|[.])"],
  plugins: ["prettier-plugin-svelte", "@ianvs/prettier-plugin-sort-imports"],
  overrides: [
    {
      files: ["tsconfig.json", "jsconfig.json"],
      options: {
        parser: "jsonc",
      },
    },
  ],
};
