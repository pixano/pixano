/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import type { CreateObjectSchemaDefinition } from "../types/datasetItemWorkspaceTypes";

export const listInputSchema = z.object({
  name: z.string(),
  label: z.string(),
  type: z.literal("list"),
  required: z.boolean().optional(),
  options: z.array(z.object({ value: z.string(), label: z.string() })),
});

export const otherInputSchema = z.object({
  name: z.string(),
  label: z.string(),
  type: z.enum(["int", "float", "bool", "str"]),
  required: z.boolean().optional(),
});

export const createObjectInputsSchema = z.array(z.union([listInputSchema, otherInputSchema]));

export type InputFeatures = z.infer<typeof createObjectInputsSchema>;

export const mapInputsToValueType = (setupArray: InputFeatures) =>
  setupArray.reduce<CreateObjectSchemaDefinition>((acc, cur) => {
    console.log("fefe", cur);
    if (cur.type === "str" || cur.type === "list") {
      acc[cur.name] = z.string();
    } else if (cur.type === "int" || cur.type === "float") {
      acc[cur.name] = z.number();
    } else {
      acc[cur.name] = z.boolean();
    }
    if (!cur.required) {
      acc[cur.name] = acc[cur.name]?.optional();
    }
    return acc;
  }, {});

export const createSchemaFromFeatures = (setupArray: InputFeatures) => {
  return z.object(mapInputsToValueType(setupArray));
};
