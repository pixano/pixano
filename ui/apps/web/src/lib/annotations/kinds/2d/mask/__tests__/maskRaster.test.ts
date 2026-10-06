/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, describe, expect, it, vi } from "vitest";

import { createMaskCanvas, decodeMask, encodeMask } from "../maskRaster";
import { rleFrString } from "$lib/utils/maskUtils";

/**
 * The test DOM has no `OffscreenCanvas`, so these tests install a minimal fake.
 * It implements only what the raster layer actually calls — an RGBA buffer plus
 * `getImageData` / `createImageData` / `putImageData` — which is enough to
 * exercise the encode/decode contract (column-major order, alpha as
 * foreground) without pulling in a real canvas implementation. Anything
 * requiring genuine rasterisation (brush strokes, `source-in` tinting) is left
 * to manual verification; it is drawing, not data.
 */
class FakeImageData {
  readonly data: Uint8ClampedArray;
  constructor(
    readonly width: number,
    readonly height: number,
  ) {
    this.data = new Uint8ClampedArray(width * height * 4);
  }
}

class FakeOffscreenCanvas {
  private buffer: FakeImageData;
  constructor(
    readonly width: number,
    readonly height: number,
  ) {
    this.buffer = new FakeImageData(width, height);
  }
  getContext(): {
    createImageData: (w: number, h: number) => FakeImageData;
    putImageData: (d: FakeImageData) => void;
    getImageData: () => FakeImageData;
  } {
    return {
      createImageData: (w: number, h: number) => new FakeImageData(w, h),
      putImageData: (d: FakeImageData) => {
        this.buffer = d;
      },
      getImageData: () => this.buffer,
    };
  }
  /** Test-only: set a pixel's alpha, mirroring what a brush stroke would do. */
  setOpaque(x: number, y: number): void {
    this.buffer.data[(y * this.width + x) * 4 + 3] = 255;
  }
}

function installFakeCanvas(): void {
  vi.stubGlobal("OffscreenCanvas", FakeOffscreenCanvas);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("createMaskCanvas", () => {
  it("returns null when the runtime has no OffscreenCanvas", () => {
    // The guard that lets the renderer degrade instead of throwing.
    expect(createMaskCanvas([4, 4])).toBeNull();
  });

  it("sizes the canvas as (width, height) from a (height, width) grid", () => {
    installFakeCanvas();
    const canvas = createMaskCanvas([3, 5]);
    expect(canvas).not.toBeNull();
    expect(canvas!.width).toBe(5);
    expect(canvas!.height).toBe(3);
  });

  it("rejects a degenerate grid", () => {
    installFakeCanvas();
    expect(createMaskCanvas([0, 0])).toBeNull();
    expect(createMaskCanvas([-1, 4])).toBeNull();
  });
});

describe("decodeMask", () => {
  it("returns null without OffscreenCanvas", () => {
    expect(decodeMask({ size: [4, 4], counts: "a2b1" })).toBeNull();
  });

  it("returns null for an empty encoding", () => {
    installFakeCanvas();
    expect(decodeMask({ size: [4, 4], counts: "" })).toBeNull();
  });
});

describe("encodeMask", () => {
  it("returns null for a blank canvas", () => {
    // A blank raster encodes as one background run; committing it would create
    // a mask the backend stores as its empty sentinel.
    installFakeCanvas();
    const canvas = createMaskCanvas([4, 4])!;
    expect(encodeMask(canvas)).toBeNull();
  });

  it("encodes painted pixels in column-major order", () => {
    installFakeCanvas();
    const canvas = createMaskCanvas([3, 2]) as unknown as FakeOffscreenCanvas;
    // A 2-wide, 3-tall grid; paint the whole second column.
    canvas.setOpaque(1, 0);
    canvas.setOpaque(1, 1);
    canvas.setOpaque(1, 2);

    const geometry = encodeMask(canvas as unknown as OffscreenCanvas);

    expect(geometry).not.toBeNull();
    expect(geometry!.size).toEqual([3, 2]);
    // Column-major: 3 background pixels (column 0) then 3 foreground (column 1).
    expect(rleFrString(geometry!.counts)).toEqual([3, 3]);
  });

  it("round-trips a single painted pixel", () => {
    installFakeCanvas();
    const canvas = createMaskCanvas([2, 2]) as unknown as FakeOffscreenCanvas;
    canvas.setOpaque(0, 0);

    const geometry = encodeMask(canvas as unknown as OffscreenCanvas);

    // Column-major index of (0,0) is 0, so: 0 background, 1 foreground, 3 background.
    expect(rleFrString(geometry!.counts)).toEqual([0, 1, 3]);
  });
});
