/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  buildTimelineLayout,
  fillerHeight,
  revealScrollTop,
  ROW_GAP,
  SLOT_CONTENT_HEIGHT,
  slotAtY,
  slotInRange,
  verticalRenderRange,
  verticalWindowIndex,
  verticalWindowStep,
} from "../timelineLayout";
import { MARKS_ENTITY } from "../types";

// A tracking session followed by three entity rows: blocks of 32, 40, 40 and 40 px.
const layout = buildTimelineLayout([
  { key: "session", kind: "session" },
  { key: "a", kind: "entity" },
  { key: "b", kind: "entity" },
  { key: "c", kind: "entity" },
]);
// Every kind of slot: blocks of 24, 24, 40, 32 and 32 px.
const mixed = buildTimelineLayout([
  { key: "d1", kind: "detection" },
  { key: "d2", kind: "detection" },
  { key: "a", kind: "entity" },
  { key: "a/left", kind: "view" },
  { key: "a/right", kind: "view" },
]);
const empty = buildTimelineLayout([]);

describe("buildTimelineLayout", () => {
  it("stacks the slots from 0, each block owning the gap above its content", () => {
    expect(layout.slots.map((slot) => slot.top)).toEqual([0, 32, 72, 112]);
    expect(layout.slots.map((slot) => slot.height)).toEqual([32, 40, 40, 40]);
    expect(layout.slots.map((slot) => slot.contentTop)).toEqual([4, 36, 76, 116]);
    expect(layout.height).toBe(152);
  });

  it("keeps the input order, keys and kinds", () => {
    expect(layout.slots.map((slot) => [slot.key, slot.kind])).toEqual([
      ["session", "session"],
      ["a", "entity"],
      ["b", "entity"],
      ["c", "entity"],
    ]);
    expect(layout.indexByKey.get("session")).toBe(0);
    expect(layout.indexByKey.get("b")).toBe(2);
    expect(layout.indexByKey.has("zzz")).toBe(false);
  });

  it("sizes each kind of slot", () => {
    expect(mixed.slots.map((slot) => slot.top)).toEqual([0, 24, 48, 88, 120]);
    expect(mixed.slots.map((slot) => slot.height)).toEqual([24, 24, 40, 32, 32]);
    expect(mixed.height).toBe(152);
  });

  it("draws entity rows as tall as their marks' lane", () => {
    expect(ROW_GAP).toBe(4);
    expect(SLOT_CONTENT_HEIGHT.entity).toBe(MARKS_ENTITY.rowHeight);
  });

  it("indexes a repeated key by its first slot", () => {
    const repeated = buildTimelineLayout([
      { key: "a", kind: "entity" },
      { key: "a", kind: "entity" },
    ]);

    expect(repeated.slots).toHaveLength(2);
    expect(repeated.indexByKey.get("a")).toBe(0);
  });

  it("is empty without slots", () => {
    expect(empty.slots).toEqual([]);
    expect(empty.height).toBe(0);
    expect(empty.indexByKey.size).toBe(0);
  });
});

describe("slotAtY", () => {
  it("finds the slot whose block holds y", () => {
    expect(slotAtY(layout, 0)).toBe(0);
    expect(slotAtY(layout, 31)).toBe(0);
    expect(slotAtY(layout, 31.9)).toBe(0);
    expect(slotAtY(layout, 71)).toBe(1);
    expect(slotAtY(layout, 72)).toBe(2);
    expect(slotAtY(layout, 151)).toBe(3);
  });

  it("gives a gap to the slot below it", () => {
    expect(slotAtY(layout, 32)).toBe(1);
    expect(slotAtY(layout, 35)).toBe(1);
    expect(slotAtY(layout, 112)).toBe(3);
  });

  it("is -1 outside the slots", () => {
    expect(slotAtY(layout, 152)).toBe(-1);
    expect(slotAtY(layout, 400)).toBe(-1);
    expect(slotAtY(layout, -1)).toBe(-1);
    expect(slotAtY(layout, Number.NaN)).toBe(-1);
    expect(slotAtY(empty, 0)).toBe(-1);
  });

  it("agrees with a scan of every slot", () => {
    for (const laidOut of [layout, mixed]) {
      for (let y = -2; y < laidOut.height + 2; y += 0.5) {
        const expected = laidOut.slots.findIndex(
          (slot) => slot.top <= y && y < slot.top + slot.height,
        );
        expect(slotAtY(laidOut, y)).toBe(expected);
      }
    }
  });
});

describe("fillerHeight", () => {
  it("fills the body viewport below the slots", () => {
    expect(fillerHeight(layout, 161)).toBe(9);
    expect(fillerHeight(empty, 161)).toBe(161);
  });

  it("is 0 when the slots fill the viewport or it is not measured", () => {
    expect(fillerHeight(layout, 152)).toBe(0);
    expect(fillerHeight(layout, 100)).toBe(0);
    expect(fillerHeight(layout, -20)).toBe(0);
    expect(fillerHeight(layout, Number.NaN)).toBe(0);
  });
});

describe("vertical render window", () => {
  it("steps by half the viewport, at least 80 px", () => {
    expect(verticalWindowStep(161)).toBe(81);
    expect(verticalWindowStep(400)).toBe(200);
    expect(verticalWindowStep(100)).toBe(80);
    expect(verticalWindowStep(0)).toBe(80);
    expect(verticalWindowStep(Number.NaN)).toBe(80);
  });

  it("changes window once per step of scrolling", () => {
    expect(verticalWindowIndex(0, 161)).toBe(0);
    expect(verticalWindowIndex(80, 161)).toBe(0);
    expect(verticalWindowIndex(81, 161)).toBe(1);
    expect(verticalWindowIndex(300, 161)).toBe(3);
    expect(verticalWindowIndex(250, 100)).toBe(3);
  });

  it("counts a negative or unmeasured scroll as 0", () => {
    expect(verticalWindowIndex(-30, 161)).toBe(0);
    expect(verticalWindowIndex(Number.NaN, 161)).toBe(0);
  });

  it("spans two steps above and two steps below the viewport", () => {
    expect(verticalRenderRange(0, 161)).toEqual({ y0: -162, y1: 323 });
    expect(verticalRenderRange(1, 161)).toEqual({ y0: -81, y1: 404 });
    expect(verticalRenderRange(3, 161)).toEqual({ y0: 81, y1: 566 });
    expect(verticalRenderRange(3, 100)).toEqual({ y0: 80, y1: 500 });
  });

  it("covers the viewport with margins wherever the scroll stands", () => {
    for (const viewport of [100, 161, 600]) {
      const step = verticalWindowStep(viewport);
      for (let scrollTop = 0; scrollTop <= 2000; scrollTop += 7) {
        const range = verticalRenderRange(verticalWindowIndex(scrollTop, viewport), viewport);
        expect(range.y0).toBeLessThanOrEqual(scrollTop - 2 * step);
        expect(range.y1).toBeGreaterThan(scrollTop + viewport + step);
      }
    }
  });

  it("keeps the slots that overlap the range", () => {
    const c = layout.slots[3];

    expect(slotInRange(c, { y0: 0, y1: 113 })).toBe(true);
    expect(slotInRange(c, { y0: 151, y1: 300 })).toBe(true);
    expect(slotInRange(c, { y0: 0, y1: 112 })).toBe(false);
    expect(slotInRange(c, { y0: 152, y1: 300 })).toBe(false);
    expect(layout.slots.every((slot) => slotInRange(slot, verticalRenderRange(0, 161)))).toBe(true);
  });
});

describe("revealScrollTop", () => {
  const b = layout.slots[2];
  const c = layout.slots[3];

  it("is null when the block shows whole", () => {
    expect(revealScrollTop(b, 40, 100)).toBeNull();
    expect(revealScrollTop(b, 72, 100)).toBeNull();
    expect(revealScrollTop(c, 52, 100)).toBeNull();
  });

  it("scrolls up to the top of a block above the viewport", () => {
    expect(revealScrollTop(b, 80, 100)).toBe(72);
    expect(revealScrollTop(b, 140, 100)).toBe(72);
  });

  it("scrolls down just enough to show a block below the viewport", () => {
    expect(revealScrollTop(c, 0, 100)).toBe(52);
    expect(revealScrollTop(c, 51, 100)).toBe(52);
  });

  it("shows the top of a block taller than the viewport", () => {
    const tall = { top: 50, height: 150 };

    expect(revealScrollTop(tall, 0, 100)).toBe(50);
    expect(revealScrollTop(tall, 120, 100)).toBe(50);
  });

  it("moves the least that shows a block whole", () => {
    const failures: string[] = [];
    for (const viewport of [40, 41, 100, 161]) {
      for (const slot of layout.slots) {
        const shows = (scroll: number) =>
          slot.top >= scroll && slot.top + slot.height <= scroll + viewport;
        for (let scroll = 0; scroll <= 200; scroll += 1) {
          let nearest = -1;
          for (let candidate = 0; candidate <= 300; candidate += 1) {
            if (!shows(candidate)) continue;
            if (nearest < 0 || Math.abs(candidate - scroll) < Math.abs(nearest - scroll)) {
              nearest = candidate;
            }
          }
          const expected = shows(scroll) ? null : nearest;
          const actual = revealScrollTop(slot, scroll, viewport);
          if (actual !== expected) {
            failures.push(`${slot.key} at ${scroll} in ${viewport}: ${actual}, not ${expected}`);
          }
        }
      }
    }
    expect(failures).toEqual([]);
  });

  it("counts an unmeasured viewport as empty", () => {
    expect(revealScrollTop(b, 0, Number.NaN)).toBe(72);
    expect(revealScrollTop(b, Number.NaN, 161)).toBeNull();
  });
});
