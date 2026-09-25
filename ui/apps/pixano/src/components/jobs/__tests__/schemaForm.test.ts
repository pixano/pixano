/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  confirmationsFor,
  fieldKind,
  initialValue,
  initialValues,
  missingRequired,
  modelOptions,
  modelTasks,
  proposeModels,
  toggleChoice,
  toParams,
} from "../schemaForm";
import type { JsonSchema } from "$lib/api/jobsApi";

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
    record_ids: { type: "array", items: { type: "string" }, default: [] },
    ranks: { type: "array", items: { type: "integer" } },
    matrix: { type: "array", items: { type: "array" } },
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

describe("lists of scalars", () => {
  // Independent review v2, C2: the record identifiers of a label job rendered as unsupported
  // and were dropped from the request, so the job planned nothing and ended in error.
  it("renders a list of scalars as a comma-separated field", () => {
    expect(fieldKind({ type: "array", items: { type: "string" } })).toBe("array");
    expect(fieldKind({ type: "array", items: { type: "integer" } })).toBe("array");
  });

  it("leaves a list of anything else unsupported", () => {
    expect(fieldKind({ type: "array", items: { type: "array" } })).toBe("unsupported");
    expect(fieldKind({ type: "array" })).toBe("unsupported");
  });

  it("splits what was typed on commas and trims it", () => {
    expect(toParams(FAKE_SCHEMA, { record_ids: " a, b ,,c " })).toEqual({
      record_ids: ["a", "b", "c"],
    });
  });

  it("casts the items to what the list holds", () => {
    expect(toParams(FAKE_SCHEMA, { ranks: "3, 1, deux" })).toEqual({ ranks: [3, 1] });
  });

  it("drops an empty list so the declared default applies", () => {
    expect(toParams(FAKE_SCHEMA, { record_ids: "" })).toEqual({});
    expect(toParams(FAKE_SCHEMA, { record_ids: [] })).toEqual({});
  });

  it("starts empty even when the default is an empty list", () => {
    expect(initialValue({ type: "array", items: { type: "string" }, default: [] })).toBe("");
  });
});

describe("multiple choices", () => {
  // Step 2, lot 1: the media types a job covers.
  const media: JsonSchema = {
    type: "array",
    items: { type: "string", enum: ["image", "video", "point_cloud", "text"] },
    default: ["image"],
  };

  it("renders a list drawn from a fixed set as choices", () => {
    expect(fieldKind(media)).toBe("choices");
  });

  it("starts on the declared default", () => {
    expect(initialValue(media)).toEqual(["image"]);
  });

  it("ticks and unticks in the declared order", () => {
    const ticked = toggleChoice(media, ["point_cloud"], "image");
    expect(ticked).toEqual(["image", "point_cloud"]);
    expect(toggleChoice(media, ticked, "image")).toEqual(["point_cloud"]);
  });

  it("names an empty selection the schema wants non-empty as missing", () => {
    // Review of step 2, lot 1: sent empty, the job was refused with a bare 422.
    const schema: JsonSchema = { properties: { media: { ...media, minItems: 1 } } };
    expect(missingRequired(schema, { media: [] })).toEqual(["media"]);
    expect(missingRequired(schema, { media: ["image"] })).toEqual([]);
  });

  it("sends an empty selection rather than letting the default run", () => {
    const schema: JsonSchema = { properties: { media } };
    expect(toParams(schema, { media: [] })).toEqual({ media: [] });
  });
});

describe("confirmationsFor", () => {
  const schema: JsonSchema = {
    properties: {
      model: { type: "string" },
      replace_existing_embeddings: {
        type: "boolean",
        default: false,
        "x-pixano-confirm": "This deletes every vector already computed.",
      },
    },
  };

  it("asks nothing while the destructive parameter is off", () => {
    expect(confirmationsFor(schema, { replace_existing_embeddings: false })).toEqual([]);
  });

  it("gives the parameter's text once it is set", () => {
    expect(confirmationsFor(schema, { replace_existing_embeddings: true })).toEqual([
      "This deletes every vector already computed.",
    ]);
  });
});

describe("a model field", () => {
  // What the detection kind publishes: a required model, named by task and not by name.
  const detection: JsonSchema = {
    properties: {
      model: { type: "string", minLength: 1, "x-pixano-model-task": "detection" } as JsonSchema,
      box_threshold: { type: "number", default: 0.5 },
    },
    required: ["model"],
  };
  const embeddings: JsonSchema = {
    properties: { model: { type: "string", "x-pixano-model-task": "embedding" } },
  };

  it("renders as the models served for its task", () => {
    expect(fieldKind(detection.properties.model)).toBe("model");
  });

  it("names each task the kinds need once", () => {
    expect(modelTasks([detection, embeddings, detection, FAKE_SCHEMA])).toEqual([
      "detection",
      "embedding",
    ]);
  });

  it("proposes the first model the inference serves for its task", () => {
    const values = proposeModels(detection, initialValues(detection), {
      detection: ["yolo26s", "yolov8n"],
      embedding: ["clip"],
    });

    expect(values).toEqual({ model: "yolo26s", box_threshold: 0.5 });
  });

  it("keeps a model the user already chose", () => {
    const values = proposeModels(detection, { model: "yolov8n" }, { detection: ["yolo26s"] });

    expect(values.model).toBe("yolov8n");
  });

  it("lists a model typed before the served ones arrived, so the list shows what will run", () => {
    // Independent review of lot 2: the list showed the first served model, the job ran the typed one.
    expect(modelOptions(["yolo26s", "yolov8n"], "my-detector")).toEqual([
      "my-detector",
      "yolo26s",
      "yolov8n",
    ]);
    expect(modelOptions(["yolo26s"], "yolo26s")).toEqual(["yolo26s"]);
    expect(modelOptions(["yolo26s"], "")).toEqual(["yolo26s"]);
  });

  it("stays empty, and required, when the inference serves nothing for its task", () => {
    const values = proposeModels(detection, initialValues(detection), { embedding: ["clip"] });

    expect(values.model).toBe("");
    expect(missingRequired(detection, values)).toEqual(["model"]);
  });
});
