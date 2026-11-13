/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import { toRawAnnotation } from "$lib/api/adapters";
import {
  Annotation,
  BaseSchema,
  initDisplayControl,
  SequenceFrame,
  WorkspaceType,
  type Item,
} from "$lib/types/dataset";
import {
  buildWorkspaceRuntimeData,
  computeWorkspaceVideoFps,
  computeWorkspaceVideoSpeed,
} from "$lib/utils/itemDataProcessing";

// Rune-using store modules cannot load under plain vitest — stub them like
// workspaceRuntime.test.ts does. The rate helpers touch none of them.
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

describe("computeWorkspaceVideoFps", () => {
  it("reads the exact frame rate from the stored timestamps", () => {
    const at25fps = Array.from({ length: 100 }, (_, i) => i / 25);
    expect(computeWorkspaceVideoFps(sequence(at25fps))).toBeCloseTo(25, 9);
    const ntsc = Array.from({ length: 200 }, (_, i) => (i * 1001) / 30000);
    expect(computeWorkspaceVideoFps(sequence(ntsc))).toBeCloseTo(29.97003, 5);
  });

  it("keeps the rate of a view with missing frames", () => {
    const sparse = { video: [0, 1, 2, 4].map((index) => frame(index, index / 30)) };
    expect(computeWorkspaceVideoFps(sparse)).toBeCloseTo(30, 9);
    expect(computeWorkspaceVideoSpeed(sparse)).toBe(33);
  });

  it("returns undefined when the rate is unknowable", () => {
    expect(computeWorkspaceVideoFps(sequence([0, 0, 0]))).toBeUndefined();
    expect(computeWorkspaceVideoFps(sequence([0]))).toBeUndefined();
    expect(computeWorkspaceVideoFps({})).toBeUndefined();
  });
});

/** Boxes as the API answers them, made into annotations. */
function boxes(...ids: string[]): Annotation[] {
  const raws = ids.map((id) =>
    toRawAnnotation(
      {
        id,
        record_id: "item-1",
        view_id: "view-1",
        entity_id: `entity-${id}`,
        coords: [0.1, 0.1, 0.2, 0.2],
        format: "xywh",
        is_normalized: true,
        confidence: 1,
        source_type: "other",
        source_name: "Pixano",
        source_metadata: "{}",
        created_at: NOW,
        updated_at: NOW,
      },
      new Map([["view-1", "image"]]),
      "bboxes",
    ),
  );
  return Annotation.deepCreateInstanceArray({ bboxes: raws }).bboxes;
}

/** A record read, as the workspace reads one it opens or reads again. */
function readRecord(annotations: Annotation[]): Annotation[] {
  return buildWorkspaceRuntimeData(
    {
      item: { id: "item-1" } as Item,
      views: {},
      ui: { datasetId: "dataset-1", type: WorkspaceType.IMAGE },
      entities: {},
      annotations: { bboxes: annotations },
    },
    { main: {}, objects: {} },
  ).annotations;
}

describe("the display state of the annotations read", () => {
  it("is each annotation's own", () => {
    const [first, second] = readRecord(boxes("a", "b"));

    first.ui.displayControl.highlighted = "none";

    expect(second.ui.displayControl.highlighted).toBe("all");
  });

  it("starts as usual on the record read after a pick dimmed the previous one's", () => {
    // The Fusion tool dims the objects it cannot merge by writing their display state in place: it
    // reached the default every annotation read shared, and every record opened afterwards was dimmed.
    for (const annotation of readRecord(boxes("a", "b"))) {
      annotation.ui.displayControl.highlighted = "none";
    }

    const [readAgain] = readRecord(boxes("c"));

    expect(readAgain.ui.displayControl.highlighted).toBe("all");
    expect(initDisplayControl.highlighted).toBe("all");
  });
});
