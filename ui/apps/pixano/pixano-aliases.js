import { fileURLToPath } from "node:url";

const appComponentsPath = fileURLToPath(new URL("./src/components", import.meta.url));

export const pixanoAliases = {
  $components: appComponentsPath,
};
