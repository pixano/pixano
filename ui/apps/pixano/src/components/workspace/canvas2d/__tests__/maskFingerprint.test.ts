/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildMaskFingerprint, type FingerprintMask } from "../maskFingerprint";

function mask(
  id: string,
  display: Partial<FingerprintMask["ui"]["displayControl"]> = {},
): FingerprintMask {
  return {
    id,
    data: { entity_id: "car" },
    ui: {
      bitmapUrl: `blob:${id}`,
      bounds: { x: 1, y: 2, width: 3, height: 4 },
      displayControl: { hidden: false, highlighted: "all", ...display },
    },
  };
}

function fingerprint(
  colorById: ReadonlyMap<string, string>,
  masks: FingerprintMask[] = [mask("m1"), mask("m2")],
  forceNeutral = false,
): string {
  return buildMaskFingerprint({
    imageWidth: 640,
    imageHeight: 480,
    forceNeutral,
    masks,
    colorById,
    preview: null,
  });
}

const COLORS = new Map([
  ["m1", "#1e90ff"],
  ["m2", "#ffff00"],
]);

describe("buildMaskFingerprint", () => {
  // Regression: the video workspace did not repaint masks when only their color changed.
  it("changes when only a mask's color changes", () => {
    const recolored = new Map(COLORS).set("m2", "#ff0000");

    expect(fingerprint(recolored)).not.toBe(fingerprint(COLORS));
  });

  it("stays the same for the same colors in a new map", () => {
    expect(fingerprint(new Map(COLORS))).toBe(fingerprint(COLORS));
  });

  it("changes with the display state and the neutral presentation", () => {
    const base = fingerprint(COLORS);

    expect(fingerprint(COLORS, [mask("m1", { hidden: true }), mask("m2")])).not.toBe(base);
    expect(fingerprint(COLORS, [mask("m1", { highlighted: "none" }), mask("m2")])).not.toBe(base);
    expect(fingerprint(COLORS, undefined, true)).not.toBe(base);
  });
});
