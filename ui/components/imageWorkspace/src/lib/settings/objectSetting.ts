import { z } from "zod";

// create inputs to create a new object
export const userObjectSetup = [
  {
    label: "Label",
    name: "category_name",
    type: "text",
    multiple: false,
    required: true,
  },
  {
    label: "actions",
    name: "actions",
    type: "text",
    multiple: true,
    required: false,
  },
  {
    label: "age",
    name: "age",
    type: "number",
    required: false,
  },
  {
    label: "enfant",
    name: "hasChildren",
    type: "checkbox",
    required: false,
  },
] as const;

// validate that inputs are in the correct format
export const textInputSchema = z.object({
  name: z.string(),
  label: z.string(),
  type: z.literal("text"),
  multiple: z.boolean().optional(),
  required: z.boolean().optional(),
});

const otherInputSchema = z.object({
  name: z.string(),
  label: z.string(),
  type: z.enum(["number", "checkbox"]),
  required: z.boolean().optional(),
});

const objectInputSchema = z.array(z.union([textInputSchema, otherInputSchema]));
export const objectSetup = objectInputSchema.parse(userObjectSetup);

export const schema = userObjectSetup.reduce<Record<string, z.ZodTypeAny>>((acc, cur) => {
  if (cur.type === "text") {
    acc[cur.label] = z.array(z.string());
  } else if (cur.type === "number") {
    acc[cur.label] = z.number();
  } else {
    acc[cur.label] = z.boolean();
  }
  if (!cur.required) {
    acc[cur.label] = acc[cur.label]?.optional();
  }
  return acc;
}, {});

export const objectValidationSchema = z.object(schema);

// import { z } from "zod";

// import type { ObjectPropertySetup } from "@pixano/core";

// export const objectSetup: ObjectPropertySetup[] = [
//   {
//     label: "name",
//     type: "text",
//     multiple: false,
//     required: true,
//   },
//   {
//     label: "actions",
//     type: "text",
//     multiple: true,
//     required: false,
//   },
//   {
//     label: "age",
//     type: "number",
//     required: false,
//   },
//   {
//     label: "enfant",
//     type: "checkbox",
//     required: false,
//   },
// ];

// const otherSchema: z.ZodTypeAny[] = objectSetup.map((object) => {
//   let type: z.ZodTypeAny = z.string();
//   if (object.type === "text") {
//     type = z.array(z.string());
//     if (!object.multiple) {
//       type = z.array(z.string().min(1));
//     }
//   } else if (object.type === "number") {
//     type = z.number();
//   } else if (object.type === "checkbox") {
//     type = z.boolean();
//   }
//   if (!object.required) {
//     type = type.optional();
//   }
//   return type;
// });

// export const schema = objectSetup.reduce(
//   (acc, cur) => {
//     if (cur.type === "text") {
//       acc[cur.label] = z.array(z.string());
//       if (!cur.multiple) {
//         acc[cur.label] = z.array(z.string());
//       }
//     } else if (cur.type === "number") {
//       acc[cur.label] = z.number().optional();
//     } else if (cur.type === "checkbox") {
//       acc[cur.label] = z.boolean().optional();
//     }
//     if (!cur.required) {
//       acc[cur.label] = acc[cur.label].optional();
//     }
//     return acc;
//   },
//   {} as Record<string, z.ZodTypeAny>,
// );

// // export const objectCreationFormSchema = z.tuple([otherSchema[0], ...otherSchema.slice(1)]);

// export const objectSchema = z.object(schema);
