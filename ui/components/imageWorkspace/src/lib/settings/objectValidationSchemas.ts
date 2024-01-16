import type { ItemFeature } from "@pixano/core";
import { z } from "zod";
import type { CreateObjectSchemaDefinition } from "../types/imageWorkspaceTypes";

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
  type: z.enum(["number", "boolean", "text"]),
  required: z.boolean().optional(),
});

export const createObjectInputsSchema = z.array(z.union([listInputSchema, otherInputSchema]));

export const mapInputsToValueType = (setupArray: ItemFeature[]) =>
  setupArray.reduce<CreateObjectSchemaDefinition>((acc, cur) => {
    if (cur.dtype === "text" || cur.dtype === "list") {
      acc[cur.name] = z.string();
    } else if (cur.dtype === "number") {
      acc[cur.name] = z.number();
    } else {
      acc[cur.name] = z.boolean();
    }
    if (!cur.required) {
      acc[cur.name] = acc[cur.name]?.optional();
    }
    return acc;
  }, {});

export const createSchemaFromFeatures = (setupArray: ItemFeature[]) => {
  return z.object(mapInputsToValueType(setupArray));
};
