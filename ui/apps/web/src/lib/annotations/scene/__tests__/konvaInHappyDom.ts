/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Lets the real Konva run under happy-dom, for the tests where a mocked Konva
 * would hide the very thing under test — which node an event reaches, what a
 * `Konva.Transformer` leaves on the node it resizes.
 *
 * happy-dom has no 2D canvas, so every canvas hands out a context that takes
 * every drawing call and draws nothing: what these tests read is the node tree
 * and its events, never pixels.
 *
 * Konva's default entry for Node also needs the native `canvas` package; its
 * browser build does not. Each test file loads that build itself, as `vi.mock`
 * applies to the file that calls it:
 *
 *   vi.mock("konva", async () => ({
 *     default: (await vi.importActual<{ default: unknown }>("konva/lib/index.js")).default,
 *   }));
 */

/** Red, green, blue and alpha: the channels of one pixel of image data. */
const CHANNELS_PER_PIXEL = 4;

const doNothing = () => undefined;

/** The calls whose answer Konva reads back; any other call draws, and returns nothing. */
const ANSWERS: Record<string, () => unknown> = {
  measureText: () => ({ width: 0, actualBoundingBoxAscent: 0, actualBoundingBoxDescent: 0 }),
  getImageData: () => ({ data: new Uint8ClampedArray(CHANNELS_PER_PIXEL) }),
  createImageData: () => ({ data: new Uint8ClampedArray(CHANNELS_PER_PIXEL) }),
  createLinearGradient: () => ({ addColorStop: doNothing }),
  createRadialGradient: () => ({ addColorStop: doNothing }),
  createPattern: () => ({}),
  isPointInPath: () => false,
  isPointInStroke: () => false,
  getLineDash: () => [],
};

function silentContext(canvas: HTMLCanvasElement): CanvasRenderingContext2D {
  const state: Record<string | symbol, unknown> = { canvas };
  return new Proxy(state, {
    get: (target, key) => {
      if (key in target) return target[key];
      return typeof key === "string" && key in ANSWERS ? ANSWERS[key] : doNothing;
    },
    set: (target, key, value) => {
      target[key] = value;
      return true;
    },
  }) as unknown as CanvasRenderingContext2D;
}

/** Give every canvas of the test document a 2D context that draws nothing. */
export function installSilentCanvas(): void {
  HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement) {
    return silentContext(this);
  } as unknown as typeof HTMLCanvasElement.prototype.getContext;
}
