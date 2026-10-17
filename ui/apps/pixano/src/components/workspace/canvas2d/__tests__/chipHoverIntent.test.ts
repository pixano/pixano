/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createChipHoverIntent, type ChipHoverIntent } from "../chipHoverIntent";

describe("createChipHoverIntent", () => {
  let changes: Array<string | null>;
  let intent: ChipHoverIntent;

  beforeEach(() => {
    vi.useFakeTimers();
    changes = [];
    intent = createChipHoverIntent((key) => changes.push(key), undefined, {
      show: 100,
      switch: 150,
      close: 300,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows after a pause on a box, not on a quick sweep", () => {
    intent.pointerOn("a");
    vi.advanceTimersByTime(60);
    intent.pointerOn("b");
    vi.advanceTimersByTime(60);
    intent.pointerOn(null);
    vi.advanceTimersByTime(1000);
    expect(changes).toEqual([]);

    intent.pointerOn("a");
    vi.advanceTimersByTime(100);
    expect(intent.key).toBe("a");
  });

  it("keeps the delay running while the pointer moves within the same box", () => {
    intent.pointerOn("a");
    vi.advanceTimersByTime(50);
    intent.pointerOn("a");
    vi.advanceTimersByTime(50);
    expect(intent.key).toBe("a");
  });

  it("switches boxes after the longer delay, and ignores a brief crossing", () => {
    intent.pointerOn("a");
    vi.advanceTimersByTime(100);
    intent.pointerOn("b");
    vi.advanceTimersByTime(100);
    intent.pointerOn("a");
    vi.advanceTimersByTime(500);
    expect(changes).toEqual(["a"]);

    intent.pointerOn("b");
    vi.advanceTimersByTime(150);
    expect(changes).toEqual(["a", "b"]);
  });

  it("lingers after leaving a box and stays while the pointer is on the chip", () => {
    intent.pointerOn("a");
    vi.advanceTimersByTime(100);
    intent.pointerOn(null);
    vi.advanceTimersByTime(200);
    intent.enterChip();
    vi.advanceTimersByTime(1000);
    expect(intent.key).toBe("a");

    intent.leaveChip();
    vi.advanceTimersByTime(300);
    expect(intent.key).toBeNull();
  });

  it("stays put while frozen, then catches up", () => {
    intent.pointerOn("a");
    vi.advanceTimersByTime(100);
    intent.freeze();
    intent.pointerOn("b");
    vi.advanceTimersByTime(1000);
    expect(intent.key).toBe("a");

    intent.unfreeze();
    vi.advanceTimersByTime(150);
    expect(intent.key).toBe("b");
  });

  it("drops the chip at once on reset", () => {
    intent.pointerOn("a");
    vi.advanceTimersByTime(100);
    intent.enterChip();
    intent.reset();
    expect(intent.key).toBeNull();
    expect(changes).toEqual(["a", null]);
  });
});
