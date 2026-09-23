/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  buildLerobotSchemaSpec,
  DEFAULT_LEROBOT_FIELDS,
  validateLerobotFields,
  type LerobotFields,
} from "../lerobotSchema";
import type { AttrRow } from "../rawSchema";

const fields = (overrides: Partial<LerobotFields> = {}): LerobotFields => ({
  ...structuredClone(DEFAULT_LEROBOT_FIELDS),
  ...overrides,
});

const attr = (overrides: Partial<AttrRow> = {}): AttrRow => ({
  name: "category",
  type: "str",
  list: false,
  required: false,
  defaultValue: "",
  ...overrides,
});

describe("buildLerobotSchemaSpec", () => {
  it("keeps the existing LeRobot tools without declaring source views or fields", () => {
    expect(buildLerobotSchemaSpec(fields())).toEqual({
      annotations: ["bbox", "mask", "tracklet"],
    });
  });

  it("serializes object and record attrs with typed defaults and selected tools", () => {
    const schema = fields({
      recordAttrs: [attr({ name: "reviewed", type: "bool", defaultValue: "false" })],
      entityAttrs: [
        attr({ required: true }),
        attr({ name: "score", type: "float", defaultValue: "0" }),
        attr({ name: "labels", list: true, defaultValue: "cup, gripper" }),
        attr({ name: "counts", type: "int", list: true, defaultValue: "0, 2" }),
        attr({ name: "visible", type: "bool", list: true, defaultValue: "true, false" }),
        attr({ name: "note" }),
      ],
      annotations: ["bbox", "multi_path"],
    });
    expect(validateLerobotFields(schema)).toBe("");
    expect(buildLerobotSchemaSpec(schema)).toEqual({
      record: { attrs: { reviewed: { type: "bool", default: false } } },
      entity: {
        attrs: {
          category: { type: "str", required: true },
          score: { type: "float", default: 0 },
          labels: { type: "str", collection: true, default: ["cup", "gripper"] },
          counts: { type: "int", collection: true, default: [0, 2] },
          visible: { type: "bool", collection: true, default: [true, false] },
          note: { type: "str" },
        },
      },
      annotations: ["bbox", "multi_path", "tracklet"],
    });
  });

  it("includes tracks automatically and drops unsupported selections from old state", () => {
    expect(buildLerobotSchemaSpec(fields({ annotations: [] }))).toEqual({
      annotations: ["tracklet"],
    });
    expect(
      buildLerobotSchemaSpec(
        fields({ annotations: ["mask", "keypoint", "classification", "relation"] }),
      ),
    ).toEqual({ annotations: ["mask", "tracklet"] });
  });
});

describe("validateLerobotFields", () => {
  it("validates names, duplicates, and typed scalar/list defaults", () => {
    expect(validateLerobotFields(fields({ entityAttrs: [attr({ name: "Bad Name" })] }))).toContain(
      "snake_case",
    );
    expect(validateLerobotFields(fields({ entityAttrs: [attr(), attr()] }))).toContain("twice");
    expect(
      validateLerobotFields(fields({ recordAttrs: [attr({ type: "bool", defaultValue: "yes" })] })),
    ).toContain("Record attribute");
    expect(
      validateLerobotFields(
        fields({ entityAttrs: [attr({ type: "int", list: true, defaultValue: "1, x" })] }),
      ),
    ).toContain("comma-separated int list");
  });

  it.each([
    "id",
    "split",
    "created_at",
    "updated_at",
    "status",
    "comment",
    "episode_index",
    "tasks",
    "length",
  ])("rejects reserved record attribute %s", (name) => {
    expect(validateLerobotFields(fields({ recordAttrs: [attr({ name })] }))).toContain(
      "provided by Pixano or the LeRobot source",
    );
  });

  it.each(["id", "record_id", "parent_id"])("rejects reserved object attribute %s", (name) => {
    expect(validateLerobotFields(fields({ entityAttrs: [attr({ name })] }))).toContain(
      "managed by Pixano",
    );
  });

  it.each(["model_dump", "model_validate", "model_config"])(
    "rejects model member %s for either attribute owner",
    (name) => {
      expect(validateLerobotFields(fields({ recordAttrs: [attr({ name })] }))).toContain(
        "reserved model_ prefix",
      );
      expect(validateLerobotFields(fields({ entityAttrs: [attr({ name })] }))).toContain(
        "reserved model_ prefix",
      );
    },
  );

  it("allows matching custom names across owners and episode-field names on entities", () => {
    expect(
      validateLerobotFields(
        fields({ recordAttrs: [attr()], entityAttrs: [attr(), attr({ name: "length" })] }),
      ),
    ).toBe("");
  });

  it("rejects required record attributes while allowing required object attributes", () => {
    expect(validateLerobotFields(fields({ recordAttrs: [attr({ required: true })] }))).toContain(
      "cannot be required",
    );
    expect(validateLerobotFields(fields({ entityAttrs: [attr({ required: true })] }))).toBe("");
  });

  it("allows the automatic object-tracks tool without an extra selection", () => {
    expect(validateLerobotFields(fields({ annotations: [] }))).toBe("");
  });
});
