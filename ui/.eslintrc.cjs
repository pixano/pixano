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
		"no-undef": "off",
		"no-unused-vars": "error",
	},
};
