/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  parseCollectionValue,
  validateEntityForm,
  type InputFeatures,
} from "../featureValidationSchemas";
import { BaseSchema } from "$lib/types/dataset";

const sch = { name: "entities", group: "entities", base_schema: BaseSchema.Entity };

describe("typed attribute validation", () => {
  it("parses all supported list types without coercion", () => {
    expect(parseCollectionValue('["a", "two, words"]', "str")).toEqual({
      value: ["a", "two, words"],
      error: "",
    });
    expect(parseCollectionValue("[1,-2]", "int")).toEqual({ value: [1, -2], error: "" });
    expect(parseCollectionValue("[0.2,1e3]", "float")).toEqual({ value: [0.2, 1000], error: "" });
    expect(parseCollectionValue("[true,false]", "bool")).toEqual({
      value: [true, false],
      error: "",
    });
    expect(parseCollectionValue("", "str")).toEqual({ value: [], error: "" });
  });

  it("rejects malformed lists, wrong element types and invalid numbers", () => {
    for (const text of [
      "1,2",
      "{}",
      '"one"',
      "[1,]",
      "[1.5]",
      "[9007199254740993]",
      "[1e400]",
      '["1"]',
    ]) {
      expect(parseCollectionValue(text, "int").error).not.toBe("");
    }
    expect(parseCollectionValue("[1]", "bool").error).not.toBe("");
    expect(parseCollectionValue("[null]", "str").error).not.toBe("");
  });

  it("requires values without treating zero or false as missing", () => {
    const inputs: InputFeatures = [
      { name: "name", label: "Name", type: "str", required: true, sch },
      { name: "count", label: "Count", type: "int", required: true, sch },
      { name: "flag", label: "Flag", type: "bool", required: true, sch },
      { name: "tags", label: "Tags", type: "collection", itemType: "str", required: true, sch },
    ];
    expect(
      validateEntityForm(inputs, {
        entities: { name: "robot", count: 0, flag: false, tags: ["a"] },
      }).success,
    ).toBe(true);
    expect(
      validateEntityForm(inputs, {
        entities: { name: " ", count: 1.2, flag: false, tags: [] },
      }).fieldErrors.map((error) => error.name),
    ).toEqual(["name", "count", "tags"]);
    expect(
      validateEntityForm(inputs, {
        entities: { name: "robot", count: Infinity, flag: false, tags: "a" },
      }).success,
    ).toBe(false);
  });
});
