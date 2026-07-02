/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { describe, expect, it } from "vitest";

import type { CoordsNorm } from "$lib/annotations/types.js";

import { getPixelFrame, normalizedToPixel, pixelToNormalized, type PixelFrame } from "../scene2dGeometry.js";

/** Minimal Konva.Image stand-in: getPixelFrame only reads x/y/width/height. */
function fakeImage(x: number, y: number, w: number, h: number): Konva.Image {
  return { x: () => x, y: () => y, width: () => w, height: () => h } as unknown as Konva.Image;
}

describe("getPixelFrame", () => {
  it("returns null when there is no image", () => {
    expect(getPixelFrame(null)).toBeNull();
  });

  it("reads the image's placement and size", () => {
    expect(getPixelFrame(fakeImage(12, 34, 640, 480))).toEqual({ x: 12, y: 34, w: 640, h: 480 });
  });
});

describe("normalizedToPixel", () => {
  it("maps normalized xywh onto a frame at the origin", () => {
    const frame: PixelFrame = { x: 0, y: 0, w: 100, h: 200 };
    expect(normalizedToPixel([0.1, 0.2, 0.3, 0.4], frame)).toEqual({ x: 10, y: 40, width: 30, height: 80 });
  });

  it("offsets by the frame position (letterboxed image)", () => {
    const frame: PixelFrame = { x: 50, y: 20, w: 100, h: 100 };
    expect(normalizedToPixel([0, 0, 1, 1], frame)).toEqual({ x: 50, y: 20, width: 100, height: 100 });
  });
});

describe("pixelToNormalized", () => {
  it("maps a pixel rect back to normalized xywh", () => {
    const frame: PixelFrame = { x: 0, y: 0, w: 100, h: 200 };
    expect(pixelToNormalized(10, 40, 30, 80, frame)).toEqual([0.1, 0.2, 0.3, 0.4]);
  });

  it("accounts for the frame offset", () => {
    const frame: PixelFrame = { x: 50, y: 20, w: 100, h: 100 };
    expect(pixelToNormalized(60, 30, 50, 50, frame)).toEqual([0.1, 0.1, 0.5, 0.5]);
  });
});

describe("round-trip", () => {
  it("pixelToNormalized ∘ normalizedToPixel is the identity", () => {
    const frame: PixelFrame = { x: 17, y: 9, w: 333, h: 271 };
    const coords: CoordsNorm = [0.12, 0.34, 0.45, 0.5];
    const px = normalizedToPixel(coords, frame);
    const back = pixelToNormalized(px.x, px.y, px.width, px.height, frame);
    back.forEach((v, i) => expect(v).toBeCloseTo(coords[i]));
  });
});
