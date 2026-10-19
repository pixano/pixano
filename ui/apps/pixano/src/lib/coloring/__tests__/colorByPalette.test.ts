/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import type { ColorByAttribute } from "../colorByCatalogue";
import {
  ATTRIBUTE_PALETTE,
  categoricalColor,
  compareValueKeys,
  createRamp,
  DEFAULT_RAMP,
  extendCategoricalOrder,
  firstKeys,
  formatAttributeNumber,
  hashSlot,
  isHexColor,
  MAX_LEARNED_VALUES,
  MAX_VALUE_KEY_LENGTH,
  NO_VALUE_COLOR,
  normalizeHexColor,
  rampPosition,
  readAttributeValue,
  resolveNumericDomain,
  UNLINKED_COLOR,
  widenRange,
} from "../colorByPalette";
import { NEUTRAL_ENTITY_COLOR } from "$lib/constants/workspaceConstants";
import { paletteColorAt } from "$lib/utils/coreUtils";

type Reading = Pick<ColorByAttribute, "scale" | "fieldType" | "noValueBelow">;
const STR: Reading = { scale: "categorical", fieldType: "str" };
const BOOL: Reading = { scale: "categorical", fieldType: "bool" };
const FLOAT: Reading = { scale: "numeric", fieldType: "float" };
const CONFIDENCE: Reading = { scale: "numeric", fieldType: "float", noValueBelow: 0 };

const HEX = /^#[0-9a-f]{6}$/;

describe("palette constants", () => {
  it("are distinct hex colors from the entity palette, without its pink", () => {
    const entityPalette = new Set(Array.from({ length: 32 }, (_, i) => paletteColorAt(i)));

    expect(new Set(ATTRIBUTE_PALETTE).size).toBe(ATTRIBUTE_PALETTE.length);
    for (const color of ATTRIBUTE_PALETTE) {
      expect(color).toMatch(HEX);
      expect(entityPalette.has(color)).toBe(true);
    }
    expect(ATTRIBUTE_PALETTE).not.toContain(UNLINKED_COLOR);
    expect(ATTRIBUTE_PALETTE).not.toContain(NO_VALUE_COLOR);
  });

  it("keep the no-value color opaque and apart from the de-emphasis gray", () => {
    expect(NO_VALUE_COLOR).toMatch(HEX);
    expect(normalizeHexColor(NEUTRAL_ENTITY_COLOR)).not.toBe(NO_VALUE_COLOR);
    expect(UNLINKED_COLOR).toBe("#ffc0cb");
  });
});

describe("readAttributeValue", () => {
  it.each([
    [undefined, null],
    [null, null],
    ["", null],
    ["   ", null],
    [{}, null],
    [["car"], null],
    ["car", "car"],
    ["  car ", "car"],
    [3, "3"],
    [Number.NaN, null],
    [true, "true"],
  ])("reads %j in a text field as %j", (raw, expected) => {
    expect(readAttributeValue(STR, raw)).toBe(expected);
  });

  it.each([
    [true, "true"],
    [false, "false"],
    ["True", "true"],
    [" false ", "false"],
    ["yes", null],
    [1, null],
    [undefined, null],
  ])("reads %j in a yes/no field as %j", (raw, expected) => {
    expect(readAttributeValue(BOOL, raw)).toBe(expected);
  });

  it.each([
    [0.5, 0.5],
    [0, 0],
    ["0.5", 0.5],
    [" 2 ", 2],
    ["abc", null],
    ["", null],
    [true, null],
    [Number.POSITIVE_INFINITY, null],
    [null, null],
  ])("reads %j in a numeric field as %j", (raw, expected) => {
    expect(readAttributeValue(FLOAT, raw)).toBe(expected);
  });

  it("reads a confidence below 0 as no value, and 0 as a value", () => {
    expect(readAttributeValue(CONFIDENCE, -1)).toBeNull();
    expect(readAttributeValue(CONFIDENCE, 0)).toBe(0);
    expect(readAttributeValue(CONFIDENCE, 1)).toBe(1);
  });
});

describe("compareValueKeys", () => {
  it("sorts naturally, and ties deterministically", () => {
    expect(["10", "2", "b", "a", "B"].sort(compareValueKeys)).toEqual(["2", "10", "a", "b", "B"]);
    expect(compareValueKeys("a", "a")).toBe(0);
  });
});

describe("extendCategoricalOrder", () => {
  it("puts the seeds first, then the new values in natural order", () => {
    expect(extendCategoricalOrder(undefined, ["false", "true"], ["true"])).toEqual([
      "false",
      "true",
    ]);
    expect(extendCategoricalOrder(undefined, undefined, ["truck", "car", "10", "2"])).toEqual([
      "2",
      "10",
      "car",
      "truck",
    ]);
  });

  it("keeps the place of known values and appends the new ones", () => {
    expect(extendCategoricalOrder(["truck", "car"], undefined, ["bus", "car", "auto"])).toEqual([
      "truck",
      "car",
      "auto",
      "bus",
    ]);
  });

  it("returns the same order when nothing is new", () => {
    const order = ["car", "truck"];

    expect(extendCategoricalOrder(order, undefined, ["truck"])).toBe(order);
    expect(extendCategoricalOrder(order, ["car"], [])).toBe(order);
    expect(extendCategoricalOrder(undefined, undefined, [])).toEqual([]);
  });

  it("remembers at most MAX_LEARNED_VALUES values, the first ones in natural order", () => {
    const many = Array.from({ length: MAX_LEARNED_VALUES + 10 }, (_, i) => `v${i}`).reverse();
    const order = extendCategoricalOrder(undefined, undefined, many);

    expect(order).toHaveLength(MAX_LEARNED_VALUES);
    expect(order[0]).toBe("v0");
    expect(order[MAX_LEARNED_VALUES - 1]).toBe(`v${MAX_LEARNED_VALUES - 1}`);
    expect(extendCategoricalOrder(order, undefined, ["new"])).toBe(order);
  });

  // An overlong value is never stored, so remembering it would be asked again on every build.
  it("never remembers an overlong value", () => {
    const long = "x".repeat(MAX_VALUE_KEY_LENGTH + 1);

    expect(extendCategoricalOrder(undefined, undefined, ["a", long])).toEqual(["a"]);
  });

  it("handles records with a huge number of distinct values", () => {
    const keys = Array.from({ length: 150_000 }, (_, i) => `value ${i}`);

    const order = extendCategoricalOrder(undefined, undefined, keys);
    expect(order).toHaveLength(MAX_LEARNED_VALUES);
    expect(extendCategoricalOrder(order, undefined, keys)).toBe(order);
  });
});

describe("firstKeys", () => {
  it("returns the first keys in natural order, sorted", () => {
    expect(firstKeys(["10", "b", "2", "a", "1"], 3)).toEqual(["1", "2", "10"]);
    expect(firstKeys(["b", "a"], 5)).toEqual(["a", "b"]);
    expect(firstKeys(["b", "a"], 0)).toEqual([]);
  });
});

describe("categoricalColor", () => {
  it("gives slot i the palette color i, wrapping around", () => {
    const slots = new Map([
      ["a", 0],
      ["b", 1],
      ["c", ATTRIBUTE_PALETTE.length],
    ]);

    expect(categoricalColor("a", slots)).toBe(ATTRIBUTE_PALETTE[0]);
    expect(categoricalColor("b", slots)).toBe(ATTRIBUTE_PALETTE[1]);
    expect(categoricalColor("c", slots)).toBe(ATTRIBUTE_PALETTE[0]);
  });

  it("prefers the user's color, read as an own property only", () => {
    const slots = new Map([["car", 0]]);

    expect(categoricalColor("car", slots, { car: "#123456" })).toBe("#123456");
    const constructorColor = categoricalColor("constructor", new Map(), {});
    expect(constructorColor).toMatch(HEX);
    expect(ATTRIBUTE_PALETTE).toContain(constructorColor);
  });

  it("colors a value with no slot by a stable hash", () => {
    expect(categoricalColor("zebra", new Map())).toBe(ATTRIBUTE_PALETTE[hashSlot("zebra")]);
    expect(hashSlot("zebra")).toBe(hashSlot("zebra"));
    expect(hashSlot("zebra")).toBeGreaterThanOrEqual(0);
    expect(hashSlot("zebra")).toBeLessThan(ATTRIBUTE_PALETTE.length);
  });
});

describe("hex colors", () => {
  it("normalizes CSS colors to lowercase #rrggbb", () => {
    expect(normalizeHexColor("#ABCDEF")).toBe("#abcdef");
    expect(normalizeHexColor("#abc")).toBe("#aabbcc");
    expect(normalizeHexColor("rgb(255, 0, 0)")).toBe("#ff0000");
    expect(normalizeHexColor("red")).toBe("#ff0000");
    expect(normalizeHexColor("not a color")).toBeNull();
    expect(normalizeHexColor("")).toBeNull();
    expect(normalizeHexColor(3)).toBeNull();
  });

  it("recognizes #rrggbb only", () => {
    expect(isHexColor("#a1b2c3")).toBe(true);
    expect(isHexColor("#A1B2C3")).toBe(true);
    expect(isHexColor("#abc")).toBe(false);
    expect(isHexColor("red")).toBe(false);
    expect(isHexColor(null)).toBe(false);
  });
});

describe("numeric ranges", () => {
  it("widens a remembered range only when values fall outside it", () => {
    const seen = { min: 0, max: 10 };

    expect(widenRange(seen, { min: 2, max: 8 })).toBe(seen);
    expect(widenRange(seen, null)).toBe(seen);
    expect(widenRange(seen, { min: -5, max: 8 })).toEqual({ min: -5, max: 10 });
    expect(widenRange(undefined, { min: 1, max: 2 })).toEqual({ min: 1, max: 2 });
    expect(widenRange(undefined, null)).toBeUndefined();
  });

  it("prefers the attribute's own range to the values seen", () => {
    expect(resolveNumericDomain([0, 1], { min: 5, max: 9 })).toEqual({
      min: 0,
      max: 1,
      source: "fixed",
    });
    expect(resolveNumericDomain(undefined, { min: 5, max: 9 })).toEqual({
      min: 5,
      max: 9,
      source: "seen",
    });
    expect(resolveNumericDomain(undefined, undefined)).toBeNull();
  });

  it("places values on the ramp, clamped, and a one-value range in the middle", () => {
    const domain = { min: 0, max: 10 };

    expect(rampPosition(0, domain)).toBe(0);
    expect(rampPosition(5, domain)).toBe(0.5);
    expect(rampPosition(10, domain)).toBe(1);
    expect(rampPosition(-3, domain)).toBe(0);
    expect(rampPosition(42, domain)).toBe(1);
    expect(rampPosition(7, { min: 7, max: 7 })).toBe(0.5);
    expect(rampPosition(7, null)).toBe(0.5);
  });
});

describe("createRamp", () => {
  it("ends exactly on its two colors and only returns hex", () => {
    const ramp = createRamp();

    expect(ramp.low).toBe(DEFAULT_RAMP.low);
    expect(ramp.high).toBe(DEFAULT_RAMP.high);
    expect(ramp.colorAt(0)).toBe(DEFAULT_RAMP.low);
    expect(ramp.colorAt(1)).toBe(DEFAULT_RAMP.high);
    for (let t = 0; t <= 1; t += 0.05) expect(ramp.colorAt(t)).toMatch(HEX);
    expect(ramp.colorAt(0.5)).not.toBe(ramp.low);
    expect(ramp.colorAt(0.5)).not.toBe(ramp.high);
  });

  it("clamps positions and treats a non-number as the middle", () => {
    const ramp = createRamp();

    expect(ramp.colorAt(-1)).toBe(ramp.low);
    expect(ramp.colorAt(2)).toBe(ramp.high);
    expect(ramp.colorAt(Number.NaN)).toBe(ramp.colorAt(0.5));
  });

  it("spreads stops evenly, and handles gray ends", () => {
    const ramp = createRamp("#808080", "#ffffff");
    const stops = ramp.stops(9);

    expect(stops).toHaveLength(9);
    expect(stops[0]).toBe("#808080");
    expect(stops[8]).toBe("#ffffff");
    for (const stop of stops) expect(stop).toMatch(HEX);
    expect(ramp.stops(1)).toEqual([ramp.colorAt(0.5)]);
  });

  it("reuses the ramp of the same two colors", () => {
    expect(createRamp("#000000", "#ffffff")).toBe(createRamp("#000000", "#ffffff"));
  });
});

describe("formatAttributeNumber", () => {
  it("shows integers as they are and others with at most 3 decimals", () => {
    expect(formatAttributeNumber(3)).toBe("3");
    expect(formatAttributeNumber(0.5)).toBe("0.5");
    expect(formatAttributeNumber(0.123456)).toBe("0.123");
  });
});
