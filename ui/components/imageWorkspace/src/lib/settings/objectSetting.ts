type ObjectParameters = {
  label: string;
  type: "text" | "number" | "checkbox";
  multiple: boolean;
  mandatory: boolean;
};

export const objectSetup: ObjectParameters[] = [
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
    multiple: false,
    mandatory: false,
  },
  {
    label: "enfant",
    type: "checkbox",
    multiple: false,
    mandatory: false,
  },
];
