/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { fieldKind, initialValue, initialValues, missingRequired, toParams } from "../schemaForm";
import type { JsonSchema } from "$lib/api/jobs";

// The shape pydantic actually publishes for a job kind, trimmed to what matters here.
const FAKE_SCHEMA: JsonSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    task_count: { type: "integer", default: 200, minimum: 1 },
    seconds_per_task: { type: "number", default: 0.01 },
    label: { type: "string" },
    dry_run: { type: "boolean", default: false },
    mode: { type: "string", enum: ["fast", "thorough"] },
    fail_at_chunk: { anyOf: [{ type: "integer" }, { type: "null" }], default: null },
    nested: { type: "object", properties: {} },
  },
  required: ["task_count", "label"],
} as JsonSchema;

describe("fieldKind", () => {
  it("reads the declared type", () => {
    expect(fieldKind({ type: "integer" })).toBe("integer");
    expect(fieldKind({ type: "boolean" })).toBe("boolean");
  });

  it("prefers an enumeration over its underlying type", () => {
    expect(fieldKind({ type: "string", enum: ["a", "b"] })).toBe("enum");
  });

  it("looks through the null branch of an optional parameter", () => {
    // pydantic writes optionals as anyOf[type, null]; without this every optional field
    // would render as unsupported.
    expect(fieldKind({ anyOf: [{ type: "integer" }, { type: "null" }] })).toBe("integer");
  });

  it("reports a shape it cannot render rather than guessing", () => {
    expect(fieldKind({ type: "object" })).toBe("unsupported");
    expect(fieldKind({ type: "array" })).toBe("unsupported");
    expect(fieldKind({ anyOf: [{ type: "integer" }, { type: "string" }] })).toBe("unsupported");
  });
});

describe("initialValue", () => {
  it("uses the declared default", () => {
    expect(initialValue({ type: "integer", default: 200 })).toBe(200);
  });

  it("keeps a falsy default rather than replacing it", () => {
    expect(initialValue({ type: "boolean", default: false })).toBe(false);
    expect(initialValue({ type: "integer", default: 0 })).toBe(0);
  });

  it("starts an enumeration on its first value", () => {
    expect(initialValue({ enum: ["fast", "thorough"] })).toBe("fast");
  });

  it("seeds every parameter of a kind", () => {
    expect(initialValues(FAKE_SCHEMA)).toMatchObject({
      task_count: 200,
      seconds_per_task: 0.01,
      dry_run: false,
      mode: "fast",
      label: "",
    });
  });
});

describe("toParams", () => {
  it("converts what inputs give back as strings", () => {
    const params = toParams(FAKE_SCHEMA, { task_count: "50", seconds_per_task: "0.5" });

    expect(params.task_count).toBe(50);
    expect(params.seconds_per_task).toBe(0.5);
  });

  it("drops an untouched field so its declared default applies", () => {
    // Sending "" would be refused for its type, while omitting it means "leave it alone",
    // which is what an empty field expresses.
    expect(toParams(FAKE_SCHEMA, { task_count: "10", label: "" })).toEqual({ task_count: 10 });
  });

  it("keeps a false boolean, which is a value like any other", () => {
    expect(toParams(FAKE_SCHEMA, { dry_run: false })).toEqual({ dry_run: false });
  });

  it("ignores a number that is not one", () => {
    expect(toParams(FAKE_SCHEMA, { task_count: "beaucoup" })).toEqual({});
  });
});

describe("missingRequired", () => {
  it("names the required fields left empty", () => {
    expect(missingRequired(FAKE_SCHEMA, { task_count: "", label: "" })).toEqual([
      "task_count",
      "label",
    ]);
  });

  it("is satisfied once they are filled", () => {
    expect(missingRequired(FAKE_SCHEMA, { task_count: "5", label: "run" })).toEqual([]);
  });

  it("counts zero as filled in", () => {
    // Refusing 0 would make a legitimate value impossible to submit.
    expect(
      missingRequired({ ...FAKE_SCHEMA, required: ["task_count"] }, { task_count: 0 }),
    ).toEqual([]);
  });
});
