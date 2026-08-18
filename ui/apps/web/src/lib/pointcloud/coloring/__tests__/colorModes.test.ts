/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { COLOR_MODES_3D, colorModeFor, DEFAULT_COLOR_MODE_ID } from "../registry.js";
import { makeColorBuffer, makeColorSource } from "./fakeColorSource.js";

/**
 * Registration is the one step of adding a colour mode that nothing else
 * covers: `COLOR_MODES_3D` is a plain list, so a forgotten line leaves the code
 * compiling, every mode's own test green, and the mode simply absent from the
 * menu. These checks are what make the explicit registry line safe to prefer
 * over globbing the modes directory.
 *
 * They are also the contract every future mode inherits — a mode added without
 * reading `colorMode.ts` still has to satisfy them.
 */

const POINTS: [number, number, number, number, number][] = [
  [0, 0, 0, 0, 0],
  [1, 2, 3, 40, 1],
  [-4, 5, -6, 200, 2],
];

describe("point-cloud colour mode registry", () => {
  it("registers at least one mode", () => {
    expect(COLOR_MODES_3D.length).toBeGreaterThan(0);
  });

  it("gives every mode a unique id", () => {
    const ids = COLOR_MODES_3D.map((mode) => mode.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("gives every mode a label and an icon", () => {
    // Both are what the menu renders; a mode missing one shows up as a blank row.
    for (const mode of COLOR_MODES_3D) {
      expect(mode.label.length, `mode "${mode.id}" has no label`).toBeGreaterThan(0);
      expect(mode.icon, `mode "${mode.id}" has no icon`).toBeTruthy();
    }
  });

  it("registers the default mode", () => {
    expect(COLOR_MODES_3D.map((mode) => mode.id)).toContain(DEFAULT_COLOR_MODE_ID);
  });

  it("keeps the default mode usable on a bare cloud", () => {
    // The widget opens with it, before any camera or calibration is known, so a
    // default that needs either would leave a new record uncoloured.
    const bare = makeColorSource([[0, 0, 0]]);
    expect(colorModeFor(DEFAULT_COLOR_MODE_ID).unavailableReason?.(bare) ?? null).toBeNull();
  });
});

describe("colorModeFor", () => {
  it("resolves a registered id", () => {
    for (const mode of COLOR_MODES_3D) {
      expect(colorModeFor(mode.id)).toBe(mode);
    }
  });

  it("falls back to the default for an unknown id", () => {
    // A persisted choice outlives the mode that produced it if one is renamed.
    expect(colorModeFor("mode-from-a-previous-release").id).toBe(DEFAULT_COLOR_MODE_ID);
  });

  it("falls back to the default when no id is stored", () => {
    expect(colorModeFor(undefined).id).toBe(DEFAULT_COLOR_MODE_ID);
  });
});

describe("every registered colour mode", () => {
  /** Modes that can run on a plain cloud with no camera and no calibration. */
  const availableModes = COLOR_MODES_3D.filter(
    (mode) => (mode.unavailableReason?.(makeColorSource(POINTS)) ?? null) === null,
  );

  it("has at least one mode that runs on an uncalibrated cloud", () => {
    expect(availableModes.length).toBeGreaterThan(0);
  });

  for (const mode of COLOR_MODES_3D) {
    describe(mode.id, () => {
      it("reports availability without throwing on an empty cloud", () => {
        // The menu asks every mode this on each render, including before the
        // cloud has any points.
        const empty = makeColorSource([]);
        expect(() => mode.unavailableReason?.(empty)).not.toThrow();
      });

      it("handles an empty cloud without writing anything", async () => {
        const source = makeColorSource([]);
        const out = makeColorBuffer(0);
        await mode.computeColors(source, out, new AbortController().signal);
        expect(out.length).toBe(0);
      });
    });
  }

  for (const mode of availableModes) {
    describe(`${mode.id} (available here)`, () => {
      it("fills every colour component it claims", async () => {
        // The buffer is reused across mode switches, so a mode that skips points
        // would leave the previous mode's colours showing through. Pre-filled
        // with an impossible -1 to catch exactly that.
        const source = makeColorSource(POINTS);
        const out = makeColorBuffer(source.pointCount);
        await mode.computeColors(source, out, new AbortController().signal);
        for (let i = 0; i < out.length; i++) {
          expect(out[i], `component ${i} left unwritten`).not.toBe(-1);
        }
      });

      it("stays inside the [0, 1] colour range", async () => {
        // Three.js clamps silently, so an out-of-range component is invisible
        // here and shows up as a washed-out cloud in the app.
        const source = makeColorSource(POINTS);
        const out = makeColorBuffer(source.pointCount);
        await mode.computeColors(source, out, new AbortController().signal);
        for (let i = 0; i < out.length; i++) {
          expect(out[i], `component ${i} out of range`).toBeGreaterThanOrEqual(0);
          expect(out[i], `component ${i} out of range`).toBeLessThanOrEqual(1);
        }
      });

      it("never writes NaN", async () => {
        // A single NaN component drops the whole point from the GPU buffer.
        const source = makeColorSource(POINTS);
        const out = makeColorBuffer(source.pointCount);
        await mode.computeColors(source, out, new AbortController().signal);
        expect([...out].some(Number.isNaN)).toBe(false);
      });

      it("survives a degenerate cloud where every point is identical", async () => {
        // The division-by-zero case for every normalising mode at once.
        const flat = makeColorSource([
          [1, 1, 1, 5, 0],
          [1, 1, 1, 5, 0],
        ]);
        const out = makeColorBuffer(flat.pointCount);
        await mode.computeColors(flat, out, new AbortController().signal);
        expect([...out].some(Number.isNaN)).toBe(false);
      });

      it("reports a legend whose bounds are ordered, when it reports one", async () => {
        const source = makeColorSource(POINTS);
        const out = makeColorBuffer(source.pointCount);
        const result = await mode.computeColors(source, out, new AbortController().signal);
        if (!result.legend) return;
        // Ordered low ≤ mid ≤ high: the midpoint is the median under the
        // rank-based mapping, so a legend that broke this order would be
        // describing a scale the colours do not follow.
        expect(result.legend.mid).toBeGreaterThanOrEqual(result.legend.low);
        expect(result.legend.high).toBeGreaterThanOrEqual(result.legend.mid);
        expect(typeof result.legend.ramp).toBe("function");
      });
    });
  }
});
