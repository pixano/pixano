/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createProjectionCamera, type ProjectionCameraSpec } from "../cameraPixels.js";

const IMAGE_WIDTH = 4;
const IMAGE_HEIGHT = 2;
const RGBA_CHANNELS = 4;

const SPEC: ProjectionCameraSpec = {
  id: "cam-front",
  name: "CAM_FRONT",
  url: "/media/cam-front.jpg",
  imageWidth: IMAGE_WIDTH,
  imageHeight: IMAGE_HEIGHT,
  calibration: {} as ProjectionCameraSpec["calibration"],
};

/** Stands in for the browser's image element: the test decides when it loads. */
class FakeImage {
  static created: FakeImage[] = [];

  crossOrigin = "";
  src = "";
  naturalWidth = IMAGE_WIDTH;
  naturalHeight = IMAGE_HEIGHT;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor() {
    FakeImage.created.push(this);
  }
}

describe("createProjectionCamera", () => {
  beforeEach(() => {
    FakeImage.created = [];
    vi.stubGlobal("Image", FakeImage);
    // `getContext` is overloaded per context type; the mock only has to be a 2D one.
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      drawImage: vi.fn(),
      getImageData: (_x: number, _y: number, width: number, height: number) => ({
        data: new Uint8ClampedArray(width * height * RGBA_CHANNELS),
      }),
    } as never);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("decodes again after a pass that was aborted while the image was loading", async () => {
    const camera = createProjectionCamera(SPEC);

    const leftTheMode = new AbortController();
    const aborted = camera.loadPixels(leftTheMode.signal);
    leftTheMode.abort();
    expect(await aborted).toBeNull();

    const cameBack = camera.loadPixels(new AbortController().signal);
    expect(FakeImage.created).toHaveLength(2);
    FakeImage.created[1].onload?.();

    expect(await cameBack).toMatchObject({ width: IMAGE_WIDTH, height: IMAGE_HEIGHT });
  });

  it("stops the download of an image nobody waits for", async () => {
    const camera = createProjectionCamera(SPEC);
    const controller = new AbortController();

    const aborted = camera.loadPixels(controller.signal);
    controller.abort();
    await aborted;

    expect(FakeImage.created[0].src).toBe("");
  });

  it("decodes an image once, however many passes ask for it", async () => {
    const camera = createProjectionCamera(SPEC);

    const first = camera.loadPixels(new AbortController().signal);
    FakeImage.created[0].onload?.();
    await first;
    const second = await camera.loadPixels(new AbortController().signal);

    expect(FakeImage.created).toHaveLength(1);
    expect(second).toMatchObject({ width: IMAGE_WIDTH, height: IMAGE_HEIGHT });
  });

  it("remembers an image that cannot be read, rather than fetching it on every pass", async () => {
    const camera = createProjectionCamera(SPEC);

    const first = camera.loadPixels(new AbortController().signal);
    FakeImage.created[0].onerror?.();
    expect(await first).toBeNull();

    expect(await camera.loadPixels(new AbortController().signal)).toBeNull();
    expect(FakeImage.created).toHaveLength(1);
  });
});
