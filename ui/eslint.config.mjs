import path from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";
import js from "@eslint/js";
import typescriptEslint from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import globals from "globals";
import svelteParser from "svelte-eslint-parser";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all,
});

export default [
  {
    ignores: [
      "**/.eslintrc.config.mjs",
      "**/.prettierrc.cjs",
      "**/svelte.config.js",
      "**/tailwind.config.cjs",
      "**/postcss.config.cjs",
      "**/vite.config.ts",
      ".svelte-kit/**/*",
      "**/mask_utils.ts",
    ],
  },
  ...compat.extends(
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended-type-checked",
    "plugin:svelte/recommended",
    "prettier",
  ),
  {
    plugins: {
      "@typescript-eslint": typescriptEslint,
    },

    languageOptions: {
      globals: {
        ...globals.browser,
      },

      parser: tsParser,
      ecmaVersion: 5,
      sourceType: "script",

      parserOptions: {
        tsconfigRootDir: "/home/jdenize/Documents/pixano/ui",
        project: ["./**/tsconfig.json"],
        extraFileExtensions: [".svelte"],
      },
    },

    rules: {
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",

      "@typescript-eslint/no-misused-promises": [
        "error",
        {
          checksVoidReturn: false,
        },
      ],
      "svelte/no-inner-declarations": "off",
    },
  },
  {
    files: ["**/*.svelte"],

    languageOptions: {
      parser: svelteParser,
      ecmaVersion: 5,
      sourceType: "script",

      parserOptions: {
        parser: "@typescript-eslint/parser",
      },
    },
  },
];
