import { z } from "zod";

import type { ObjectProperty } from "@pixano/core";

export const objectSetup: ObjectProperty[] = [
  {
    label: "name",
    type: "text",
    multiple: false,
    mandatory: true,
  },
  {
    label: "actions",
    type: "text",
    multiple: true,
    mandatory: false,
  },
  {
    label: "age",
    type: "number",
    mandatory: false,
  },
  {
    label: "enfant",
    type: "checkbox",
    mandatory: false,
  },
];

const otherSchema: z.ZodTypeAny[] = objectSetup.map((object) => {
  if (object.type === "text") {
    return z.array(z.string());
  } else if (object.type === "number") {
    return z.number().optional();
  } else if (object.type === "checkbox") {
    return z.boolean().optional();
  }
  return z.array(z.string());
});

export const schema = objectSetup.reduce(
  (acc, cur) => {
    if (cur.type === "text") {
      acc[cur.label] = z.array(z.string());
      if (!cur.multiple) {
        acc[cur.label] = z.array(z.string().length(1));
      }
    } else if (cur.type === "number") {
      acc[cur.label] = z.number().optional();
    } else if (cur.type === "checkbox") {
      acc[cur.label] = z.boolean().optional();
    }
    if (!cur.mandatory) {
      acc[cur.label] = acc[cur.label].optional();
    }
    return acc;
  },
  {} as Record<string, z.ZodTypeAny>,
);

export const objectCreationFormSchema = z.tuple([otherSchema[0], ...otherSchema.slice(1)]);

// export const objectCreationFormSchema = z.object({
//   name: z.array(z.string().length(1)),
//   actions: z.array(z.string()),
//   age: z.number().optional(),
//   enfant: z.boolean().optional(),
// });
