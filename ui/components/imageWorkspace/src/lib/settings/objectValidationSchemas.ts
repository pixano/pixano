import { z } from "zod";

// create inputs to create a new object
export const userObjectSetup = [
  {
    label: "Label",
    name: "category_name",
    type: "text",
    required: true,
  },
  {
    label: "Number of people",
    name: "people",
    type: "number",
    required: false,
  },
  {
    label: "is group",
    name: "is_group",
    type: "boolean",
    required: false,
  },
  {
    label: "Gender",
    name: "gender",
    type: "list",
    required: false,
    options: [
      { value: "F", label: "female" },
      { value: "M", label: "male" },
    ],
  },
];

// validate that inputs are in the correct format
export const listInputSchema = z.object({
  name: z.string(),
  label: z.string(),
  type: z.literal("list"),
  options: z.array(z.object({ value: z.string(), label: z.string() })),
  required: z.boolean().optional(),
});

export const otherInputSchema = z.object({
  name: z.string(),
  label: z.string(),
  type: z.enum(["number", "boolean", "text"]),
  required: z.boolean().optional(),
});

export const objectInputSchema = z.array(z.union([listInputSchema, otherInputSchema]));
export const objectSetup = objectInputSchema.parse(userObjectSetup);

export const schema = userObjectSetup.reduce<Record<string, z.ZodTypeAny>>((acc, cur) => {
  if (cur.type === "text" || cur.type === "list") {
    acc[cur.name] = z.string();
  } else if (cur.type === "number") {
    acc[cur.name] = z.number();
  } else {
    acc[cur.name] = z.boolean();
  }
  if (!cur.required) {
    acc[cur.name] = acc[cur.name]?.optional();
  }
  return acc;
}, {});

export const objectValidationSchema = z.object(schema);
