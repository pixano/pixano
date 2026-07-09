/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  buildRawSchemaSpec,
  DEFAULT_ANNOTATIONS,
  DEFAULT_RAW_FIELDS,
  parseTypedValue,
  parseViewNames,
  validateEntityAttrs,
  validateRawFields,
  type EntityAttrRow,
  type RawFields,
} from "../rawSchema";

const raw = (overrides: Partial<RawFields>): RawFields => ({
  ...structuredClone(DEFAULT_RAW_FIELDS),
  ...overrides,
});

const attr = (overrides: Partial<EntityAttrRow>): EntityAttrRow => ({
  name: "category",
  type: "str",
  list: false,
  required: false,
  defaultValue: "",
  ...overrides,
});

describe("parseViewNames", () => {
  it("splits, trims, and validates snake_case names", () => {
    expect(parseViewNames("left, right")).toEqual({ names: ["left", "right"], error: "" });
    expect(parseViewNames("")).toEqual({ names: [], error: "" });
    expect(parseViewNames("Left").error).toContain("snake_case");
    expect(parseViewNames("a b").error).toContain("snake_case");
    expect(parseViewNames("left, left").error).toContain("unique");
  });
});

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
});

describe("validateEntityAttrs", () => {
  it("rejects bad names, duplicates, and untyped defaults", () => {
    expect(validateEntityAttrs([attr({})])).toBe("");
    expect(validateEntityAttrs([attr({ name: "Bad Name" })])).toContain("snake_case");
    expect(validateEntityAttrs([attr({}), attr({})])).toContain("twice");
    expect(validateEntityAttrs([attr({ type: "int", defaultValue: "x" })])).toContain(
      "not a valid int",
    );
  });
});

describe("validateRawFields", () => {
  it("requires named views to be present and max frames numeric", () => {
    expect(validateRawFields(raw({}))).toBe("");
    expect(validateRawFields(raw({ viewsMode: "named", viewNames: "" }))).toContain("at least one");
    expect(validateRawFields(raw({ kind: "videos", maxFrames: "abc" }))).toContain("whole number");
    expect(validateRawFields(raw({ kind: "videos", maxFrames: "100" }))).toBe("");
  });
});

describe("buildRawSchemaSpec", () => {
  it("omits views in auto mode and declares them in named mode", () => {
    expect(buildRawSchemaSpec(raw({})).schema.views).toBeUndefined();
    const named = buildRawSchemaSpec(raw({ viewsMode: "named", viewNames: "left,right" }));
    expect(named.schema.views).toEqual({ left: "image", right: "image" });
  });

  it("types defaults and honours list/required flags", () => {
    const built = buildRawSchemaSpec(
      raw({
        entityAttrs: [
          attr({ name: "count", type: "int", defaultValue: "3" }),
          attr({ name: "label", required: true }),
          attr({ name: "tags", list: true }),
        ],
      }),
    );
    expect(built.schema.entity).toEqual({
      attrs: {
        count: { type: "int", default: 3 },
        label: { type: "str", required: true },
        tags: { type: "str", collection: true },
      },
    });
  });

  it("maps media kinds to workspaces and video options", () => {
    expect(buildRawSchemaSpec(raw({})).workspace).toBe("image");
    const videos = buildRawSchemaSpec(raw({ kind: "videos", maxFrames: "50" }));
    expect(videos.workspace).toBe("video");
    expect(videos.options).toEqual({ max_frames_per_video: 50 });
    const reference = buildRawSchemaSpec(raw({ kind: "videos", framesMode: "reference" }));
    expect(reference.options).toEqual({ frames: "reference" });
    expect(buildRawSchemaSpec(raw({ kind: "texts" })).workspace).toBeUndefined();
  });

  it("keeps per-kind annotation defaults distinct", () => {
    expect(DEFAULT_ANNOTATIONS.images).toContain("bbox");
    expect(DEFAULT_ANNOTATIONS.videos).toContain("tracklet");
    expect(DEFAULT_ANNOTATIONS.texts).toContain("text_span");
  });
});
