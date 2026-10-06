import path from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";
import js from "@eslint/js";
import eslint from "@eslint/js";
import typescriptEslint from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import svelte from "eslint-plugin-svelte";
import globals from "globals";
import svelteParser from "svelte-eslint-parser";
import tseslint from "typescript-eslint";

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
      "**/vitest.config.ts",
      "**/vitest.setup.ts",
      "**/pixano-aliases.js",
      // Generated output (eslint-plugin-svelte 2.x happened to skip these; with
      // 3.x they must be ignored explicitly, and the old root-relative
      // ".svelte-kit/**/*" pattern never covered the per-app directories).
      "**/.svelte-kit/**",
      "**/coverage/**",
      "apps/*/build/**",
      "**/mask_utils.ts",
    ],
  },
  ...compat.extends(
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended-type-checked",
    "prettier",
  ),
  // eslint-plugin-svelte 3.x ships native flat configs; the legacy eslintrc
  // "plugin:svelte/recommended" shareable config no longer exists.
  ...svelte.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
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
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@pixano/*/src", "@pixano/*/src/*"],
              message: "Use the package public API instead of internal src paths.",
            },
          ],
        },
      ],
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",

      "@typescript-eslint/no-misused-promises": [
        "error",
        {
          checksVoidReturn: false,
        },
      ],
      "svelte/no-inner-declarations": "off",
      // Rules newly enabled by eslint-plugin-svelte 3.x "recommended" that
      // require real refactors of existing (mostly apps/pixano) code. Disabled
      // during the 2.x → 3.x upgrade to keep it behavior-neutral; re-enable
      // rule by rule as the offending code gets cleaned up.
      "svelte/require-each-key": "off",
      "svelte/prefer-svelte-reactivity": "off",
      "svelte/no-navigation-without-resolve": "off",
      "svelte/prefer-writable-derived": "off",
      "svelte/no-useless-children-snippet": "off",
      "svelte/no-unused-props": "off",
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
