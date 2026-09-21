/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { preflightLayout } from "../layoutPreflight";
import {
  ANNOTATION_CHOICES,
  ANNOTATION_TOOLS,
  annotationsForTask,
  buildRawSchemaSpec,
  DEFAULT_ANNOTATIONS,
  DEFAULT_RAW_FIELDS,
  parseTypedListValue,
  parseTypedValue,
  validateAttrRows,
  validateRawFields,
  validateRawSchemaFields,
  validateRawVideoOptions,
  type AttrRow,
  type RawFields,
} from "../rawSchema";

const raw = (overrides: Partial<RawFields>): RawFields => ({
  ...structuredClone(DEFAULT_RAW_FIELDS),
  ...overrides,
});

const attr = (overrides: Partial<AttrRow>): AttrRow => ({
  name: "category",
  type: "str",
  list: false,
  required: false,
  defaultValue: "",
  ...overrides,
});

const entries = (...paths: string[]) => paths.map((relPath) => ({ relPath }));

describe("parseTypedValue", () => {
  it("parses per type and rejects mismatches", () => {
    expect(parseTypedValue("str", " hi ")).toBe("hi");
    expect(parseTypedValue("int", "42")).toBe(42);
    expect(parseTypedValue("int", "4.2")).toBeUndefined();
    expect(parseTypedValue("float", "-0.5")).toBe(-0.5);
    expect(parseTypedValue("float", "abc")).toBeUndefined();
    expect(parseTypedValue("bool", "true")).toBe(true);
    expect(parseTypedValue("bool", "yes")).toBeUndefined();
  });

  it("rejects defaults that would overflow JSON or lose integer precision", () => {
    expect(parseTypedValue("int", "9007199254740993")).toBeUndefined();
    expect(parseTypedValue("float", "9".repeat(400))).toBeUndefined();
    expect(parseTypedListValue("int", "0, 9007199254740993")).toBeUndefined();
  });
});

describe("parseTypedListValue", () => {
  it("parses comma-separated lists per element type", () => {
    expect(parseTypedListValue("str", "a, b")).toEqual(["a", "b"]);
    expect(parseTypedListValue("int", "1, 2, 3")).toEqual([1, 2, 3]);
    expect(parseTypedListValue("int", "1, oops")).toBeUndefined();
    expect(parseTypedListValue("str", "")).toEqual([]);
  });
});

describe("validateAttrRows", () => {
  it("rejects bad names, duplicates, and untyped defaults", () => {
    expect(validateAttrRows([attr({})])).toBe("");
    expect(validateAttrRows([attr({ name: "Bad Name" })])).toContain("snake_case");
    expect(validateAttrRows([attr({}), attr({})])).toContain("twice");
    expect(validateAttrRows([attr({ type: "int", defaultValue: "x" })])).toContain("not a valid");
  });

  it("validates list defaults as comma-separated lists", () => {
    expect(validateAttrRows([attr({ list: true, defaultValue: "a, b" })])).toBe("");
    expect(validateAttrRows([attr({ type: "int", list: true, defaultValue: "1, x" })])).toContain(
      "comma-separated int list",
    );
  });

  it("prefixes messages with the given label", () => {
    expect(validateAttrRows([attr({ name: "Bad" })], "Record attribute")).toContain(
      "Record attribute",
    );
  });

  it("ignores a hidden default when the attribute is required", () => {
    expect(
      validateAttrRows([attr({ type: "int", required: true, defaultValue: "old text" })]),
    ).toBe("");
  });
});

describe("annotation choices", () => {
  it("only offers supported tools with readable labels", () => {
    for (const task of Object.keys(ANNOTATION_CHOICES) as Array<keyof typeof ANNOTATION_CHOICES>) {
      for (const slot of [...ANNOTATION_CHOICES[task], ...DEFAULT_ANNOTATIONS[task]]) {
        expect(["keypoint", "classification", "relation"]).not.toContain(slot);
        expect(ANNOTATION_TOOLS[slot]?.label).toBeTruthy();
      }
    }
    expect(ANNOTATION_TOOLS.bbox.label).toBe("Bounding boxes");
    expect(ANNOTATION_TOOLS.multi_path.label).toBe("Polygons & lines");
  });

  it("restores required tools and removes unsupported or task-inappropriate selections", () => {
    expect(
      annotationsForTask("video", ["bbox", "keypoint", "relation", "classification", "message"]),
    ).toEqual(["bbox", "tracklet"]);
    expect(annotationsForTask("image_vqa", [])).toEqual(["message"]);
    expect(annotationsForTask("image_text_entity_linking", ["mask"])).toEqual([
      "text_span",
      "mask",
    ]);
    expect(annotationsForTask("image", ["bbox", "bbox", "tracklet"])).toEqual(["bbox"]);
  });
});

describe("validateRawVideoOptions", () => {
  it("requires a finite positive frame rate and positive integer cap", () => {
    for (const maxFrames of ["0", "-1", "1.2", "9007199254740993"]) {
      expect(validateRawVideoOptions(raw({ task: "video", maxFrames }))).toContain(
        "positive whole number",
      );
    }
    for (const fps of ["0", "-1", "Infinity", "oops"]) {
      expect(validateRawVideoOptions(raw({ task: "video", fps }))).toContain("positive number");
    }
    expect(validateRawVideoOptions(raw({ task: "video", maxFrames: "20", fps: "12.5" }))).toBe("");
  });

  it("ignores hidden extraction settings in reference mode but retains folder-frame validation", () => {
    const reference = raw({
      task: "video",
      framesMode: "reference",
      maxFrames: "invalid",
      fps: "invalid",
    });
    expect(validateRawVideoOptions(reference)).toBe("");
    reference.layout = preflightLayout(entries("clip_a/f0.jpg", "clip_b/f0.jpg"), "video");
    expect(validateRawVideoOptions(reference)).toContain("Max frames");
  });

  it("keeps source validation separate from annotation validation", () => {
    const settings = raw({ task: "video", maxFrames: "invalid" });
    expect(validateRawSchemaFields(settings)).toBe("");
    expect(validateRawFields(settings)).toContain("Max frames");
  });
});

describe("validateRawFields", () => {
  it("requires a whole number for max frames on video", () => {
    expect(validateRawFields(raw({ task: "video", maxFrames: "12.5" }))).toContain("whole number");
    expect(validateRawFields(raw({ task: "video", maxFrames: "100" }))).toBe("");
  });

  it("requires at least one annotation type", () => {
    expect(validateRawFields(raw({ annotations: [] }))).toContain("at least one annotation");
  });

  it("requires a positive fps when one is given", () => {
    expect(validateRawFields(raw({ task: "video", fps: "0" }))).toContain("FPS");
    expect(validateRawFields(raw({ task: "video", fps: "abc" }))).toContain("FPS");
    expect(validateRawFields(raw({ task: "video", fps: "24" }))).toBe("");
    expect(validateRawFields(raw({ task: "video", fps: "" }))).toBe("");
  });

  it("validates record and entity attrs separately", () => {
    expect(validateRawFields(raw({ recordAttrs: [attr({ name: "Bad" })] }))).toContain(
      "Record attribute",
    );
    expect(validateRawFields(raw({ entityAttrs: [attr({ name: "Bad" })] }))).toContain(
      "Object attribute",
    );
  });
});

describe("buildRawSchemaSpec", () => {
  it("always emits the task as the workspace", () => {
    expect(buildRawSchemaSpec(raw({ task: "image" })).workspace).toBe("image");
    expect(buildRawSchemaSpec(raw({ task: "video" })).workspace).toBe("video");
    expect(buildRawSchemaSpec(raw({ task: "image_vqa" })).workspace).toBe("image_vqa");
    expect(buildRawSchemaSpec(raw({ task: "image_text_entity_linking" })).workspace).toBe(
      "image_text_entity_linking",
    );
  });

  it("omits views for single-view layouts (backend inference applies)", () => {
    const layout = preflightLayout(entries("a.jpg", "b.jpg"), "image");
    expect(buildRawSchemaSpec(raw({ layout })).schema.views).toBeUndefined();
  });

  it("declares views from the preflight for multi-view layouts", () => {
    const layout = preflightLayout(entries("left/a.jpg", "right/a.jpg"), "image");
    expect(buildRawSchemaSpec(raw({ layout })).schema.views).toEqual({
      left: { kind: "image" },
      right: { kind: "image" },
    });
  });

  it("maps video views to sequence_frames or video by frames mode", () => {
    const layout = preflightLayout(entries("front/v.mp4", "side/v.mp4"), "video");
    const extract = buildRawSchemaSpec(raw({ task: "video", layout }));
    expect(extract.schema.views).toEqual({
      front: { kind: "sequence_frames" },
      side: { kind: "sequence_frames" },
    });
    const reference = buildRawSchemaSpec(raw({ task: "video", layout, framesMode: "reference" }));
    expect(reference.schema.views).toEqual({ front: { kind: "video" }, side: { kind: "video" } });
    expect(reference.options).toEqual({ frames: "reference" });
  });

  it("declares MEL views with their kinds", () => {
    const layout = preflightLayout(
      entries("image/a.jpg", "text/a.txt"),
      "image_text_entity_linking",
    );
    const spec = buildRawSchemaSpec(
      raw({
        task: "image_text_entity_linking",
        layout,
        annotations: [...DEFAULT_ANNOTATIONS.image_text_entity_linking],
      }),
    );
    expect(spec.workspace).toBe("image_text_entity_linking");
    expect(spec.schema.views).toEqual({ image: { kind: "image" }, text: { kind: "text" } });
    expect(spec.schema.annotations).toEqual(["text_span", "bbox", "mask"]);
  });

  it("always re-adds locked slots (a non-empty list replaces the preset backend-side)", () => {
    const spec = buildRawSchemaSpec(raw({ task: "image_vqa", annotations: ["bbox"] }));
    expect(spec.schema.annotations).toEqual(["message", "bbox"]);
    expect(
      buildRawSchemaSpec(raw({ task: "video", annotations: ["bbox"] })).schema.annotations,
    ).toEqual(["bbox", "tracklet"]);
    expect(buildRawSchemaSpec(raw({ task: "video", annotations: [] })).schema.annotations).toEqual([
      "tracklet",
    ]);
  });

  it("never serializes unsupported wizard tools from old form state", () => {
    const selected = ["bbox", "keypoint", "classification", "relation"];
    expect(buildRawSchemaSpec(raw({ annotations: selected })).schema.annotations).toEqual(["bbox"]);
    expect(selected).toEqual(["bbox", "keypoint", "classification", "relation"]);
  });

  it("emits record and entity attrs, with list defaults as arrays", () => {
    const spec = buildRawSchemaSpec(
      raw({
        recordAttrs: [attr({ name: "weather" })],
        entityAttrs: [
          attr({ name: "category", required: true }),
          attr({ name: "tags", list: true, defaultValue: "a, b" }),
        ],
      }),
    );
    expect(spec.schema.record).toEqual({ attrs: { weather: { type: "str" } } });
    expect(spec.schema.entity).toEqual({
      attrs: {
        category: { type: "str", required: true },
        tags: { type: "str", collection: true, default: ["a", "b"] },
      },
    });
  });

  it("passes the max-frames cap through for extract mode", () => {
    expect(buildRawSchemaSpec(raw({ task: "video", maxFrames: "200" })).options).toEqual({
      max_frames_per_video: 200,
    });
  });

  it("files encoding emits a sampling fps for extraction, never for reference", () => {
    const extract = buildRawSchemaSpec(raw({ task: "video", maxFrames: "50", fps: "5" }));
    expect(extract.options).toEqual({ max_frames_per_video: 50, fps: 5 });
    const reference = buildRawSchemaSpec(raw({ task: "video", framesMode: "reference", fps: "5" }));
    expect(reference.options).toEqual({ frames: "reference" });
  });

  it("folders encoding emits frames=folders with cap and fps", () => {
    const layout = preflightLayout(entries("clip_a/f0.jpg", "clip_b/f0.jpg"), "video");
    const spec = buildRawSchemaSpec(raw({ task: "video", layout, maxFrames: "50", fps: "12.5" }));
    expect(spec.schema.views).toBeUndefined(); // single view: backend inference
    expect(spec.options).toEqual({ frames: "folders", max_frames_per_video: 50, fps: 12.5 });
  });

  it("folders encoding declares sequence_frames views, ignoring framesMode", () => {
    const layout = preflightLayout(entries("front/v1/f0.jpg", "side/v1/f0.jpg"), "video");
    const spec = buildRawSchemaSpec(raw({ task: "video", layout, framesMode: "reference" }));
    expect(spec.schema.views).toEqual({
      front: { kind: "sequence_frames" },
      side: { kind: "sequence_frames" },
    });
    expect(spec.options).toEqual({ frames: "folders" });
  });

  it("emits no views from a failed preflight", () => {
    const layout = preflightLayout(entries("Left Cam/a.jpg", "left_cam/a.jpg"), "image");
    expect(layout.ok).toBe(false);
    expect(buildRawSchemaSpec(raw({ layout })).schema.views).toBeUndefined();
  });

  it("keeps per-task annotation defaults distinct", () => {
    expect(DEFAULT_ANNOTATIONS.image).toContain("bbox");
    expect(DEFAULT_ANNOTATIONS.video).toContain("tracklet");
    expect(DEFAULT_ANNOTATIONS.image_vqa).toContain("message");
    expect(DEFAULT_ANNOTATIONS.image_text_entity_linking).toContain("text_span");
  });
});
