/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import { BaseSchema, SequenceFrame } from "$lib/types/dataset";
import { computeWorkspaceVideoSpeed } from "$lib/utils/itemDataProcessing";

// Rune-using store modules cannot load under plain vitest — stub them like
// workspaceRuntime.test.ts does. computeWorkspaceVideoSpeed touches none of them.
vi.mock("$lib/stores/workspaceStores.svelte", () => ({
  entities: { value: [] },
}));

// Plain (rune-free) stand-in for the $state/$derived store primitive so the
// transitive store imports load under vitest (same escape as other util tests).
vi.mock("$lib/stores/reactiveStore.svelte", () => {
  const reactiveStore = <T>(initial: T) => {
    let value = initial;
    return {
      get value() {
        return value;
      },
      set value(next: T) {
        value = next;
      },
      update(fn: (prev: T) => T) {
        value = fn(value);
      },
    };
  };
  return {
    reactiveStore,
    reactiveRawStore: reactiveStore,
    reactiveDerived: <T>(fn: () => T) => ({
      get value() {
        return fn();
      },
    }),
  };
});

const NOW = "2026-03-31T00:00:00+00:00";

function frame(index: number, timestamp: number): SequenceFrame {
  return new SequenceFrame({
    id: `frame-${index}`,
    table_info: {
      name: "sequence_frames",
      group: "views",
      base_schema: BaseSchema.SequenceFrame,
    },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      parent_id: "",
      view_name: "video",
      frame_index: index,
      timestamp,
      url: "",
      width: 1,
      height: 1,
      format: "JPEG",
    },
  });
}

const sequence = (timestamps: number[]) => ({
  video: timestamps.map((timestamp, index) => frame(index, timestamp)),
});

describe("computeWorkspaceVideoSpeed", () => {
  it("derives milliseconds per frame from the stored timestamps", () => {
    const at25fps = Array.from({ length: 100 }, (_, i) => i / 25);
    expect(computeWorkspaceVideoSpeed(sequence(at25fps))).toBe(40);
    const at10fps = Array.from({ length: 30 }, (_, i) => i / 10);
    expect(computeWorkspaceVideoSpeed(sequence(at10fps))).toBe(100);
  });

  it("returns undefined when the rate is unknowable (the player keeps its default)", () => {
    expect(computeWorkspaceVideoSpeed(sequence([0, 0, 0]))).toBeUndefined(); // fps-unknown import
    expect(computeWorkspaceVideoSpeed(sequence([0]))).toBeUndefined(); // single frame
    expect(computeWorkspaceVideoSpeed({})).toBeUndefined(); // no sequence view at all
  });

  it("averages over strided grids so total playback matches media time", () => {
    expect(computeWorkspaceVideoSpeed(sequence([0, 0.2, 0.5, 0.7]))).toBe(233);
  });

  it("ignores non-sequence views", () => {
    const imageOnly = { image: { table_info: { base_schema: BaseSchema.Image } } as never };
    expect(computeWorkspaceVideoSpeed(imageOnly)).toBeUndefined();
  });
});
