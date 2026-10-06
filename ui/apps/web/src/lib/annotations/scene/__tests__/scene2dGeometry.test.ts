/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { describe, expect, it } from "vitest";

import {
  getPixelFrame,
  normalizedPointToPixel,
  normalizedToPixel,
  pixelToNormalized,
  type PixelFrame,
} from "../scene2dGeometry.js";
import type { CoordsNorm } from "$lib/annotations/types.js";

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
    expect(normalizedToPixel([0.1, 0.2, 0.3, 0.4], frame)).toEqual({
      x: 10,
      y: 40,
      width: 30,
      height: 80,
    });
  });

  it("offsets by the frame position (letterboxed image)", () => {
    const frame: PixelFrame = { x: 50, y: 20, w: 100, h: 100 };
    expect(normalizedToPixel([0, 0, 1, 1], frame)).toEqual({
      x: 50,
      y: 20,
      width: 100,
      height: 100,
    });
  });
});

describe("normalizedPointToPixel", () => {
  it("maps a normalized point onto a frame at the origin", () => {
    const frame: PixelFrame = { x: 0, y: 0, w: 100, h: 200 };
    expect(normalizedPointToPixel(0.1, 0.2, frame, { x: 0, y: 0 })).toEqual({ x: 10, y: 40 });
  });

  it("offsets by the frame position (letterboxed image)", () => {
    const frame: PixelFrame = { x: 50, y: 20, w: 100, h: 100 };
    expect(normalizedPointToPixel(0, 0, frame, { x: 0, y: 0 })).toEqual({ x: 50, y: 20 });
  });

  it("maps points outside the frame without clamping (corner behind/off-image)", () => {
    const frame: PixelFrame = { x: 0, y: 0, w: 100, h: 100 };
    expect(normalizedPointToPixel(-0.5, 1.5, frame, { x: 0, y: 0 })).toEqual({ x: -50, y: 150 });
  });

  // The bbox3d projection reuses one scratch point per corner, so the write
  // must land in the caller's object rather than in a fresh one.
  it("writes into the target and returns that same object", () => {
    const frame: PixelFrame = { x: 0, y: 0, w: 100, h: 200 };
    const target = { x: -1, y: -1 };
    const returned = normalizedPointToPixel(0.5, 0.5, frame, target);
    expect(returned).toBe(target);
    expect(target).toEqual({ x: 50, y: 100 });
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
