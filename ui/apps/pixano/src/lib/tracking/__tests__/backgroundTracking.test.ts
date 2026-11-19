/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import type { Job } from "$lib/api/jobsApi";
import {
  canTrackFrom,
  showTrackedBlocker,
  showTrackedLabel,
  trackingBlocker,
  trackingHint,
  trackingModel,
  trackingOutput,
  trackingParams,
  trackingSummary,
} from "$lib/tracking/backgroundTracking";
import { BaseSchema, BBox, Entity, Mask, Tracklet, WorkspaceType } from "$lib/types/dataset";

const NOW = "2026-11-05T00:00:00+00:00";

function entityWith(children: (entity: Entity) => Array<BBox | Mask | Tracklet>): Entity {
  const entity = new Entity({
    id: "car",
    table_info: { name: "entities", group: "entities", base_schema: BaseSchema.Entity },
    created_at: NOW,
    updated_at: NOW,
    data: { item_id: "record-1", parent_id: "" },
  });
  entity.ui.childs = children(entity);
  return entity;
}

function onFrame<T extends BBox | Mask>(annotation: T, frameIndex: number, inUi = true): T {
  annotation.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: false, highlighted: "all" },
    ...(inUi ? { frame_index: frameIndex } : {}),
  };
  return annotation;
}

function box(entity: Entity, frameIndex: number, inUi = true): BBox {
  return onFrame(
    new BBox({
      id: `box-${frameIndex}`,
      table_info: { name: "bboxes", group: "annotations", base_schema: BaseSchema.BBox },
      created_at: NOW,
      updated_at: NOW,
      data: {
        item_id: "record-1",
        entity_id: entity.id,
        source_type: "human",
        source_name: "",
        source_metadata: "{}",
        view_name: "video",
        inference_metadata: {},
        tracklet_id: "",
        entity_dynamic_state_id: "",
        frame_id: `frame-${frameIndex}`,
        frame_index: frameIndex,
        confidence: 1,
        coords: [0.1, 0.2, 0.3, 0.4],
        format: "xywh",
        is_normalized: true,
      },
    }),
    frameIndex,
    inUi,
  );
}

function mask(entity: Entity, frameIndex: number): Mask {
  return onFrame(
    new Mask({
      id: `mask-${frameIndex}`,
      table_info: { name: "masks", group: "annotations", base_schema: BaseSchema.Mask },
      created_at: NOW,
      updated_at: NOW,
      data: {
        item_id: "record-1",
        entity_id: entity.id,
        source_type: "human",
        source_name: "",
        source_metadata: "{}",
        view_name: "video",
        inference_metadata: {},
        tracklet_id: "",
        entity_dynamic_state_id: "",
        frame_id: `frame-${frameIndex}`,
        frame_index: frameIndex,
        size: [8, 8],
        counts: [2, 4, 58],
      },
    }),
    frameIndex,
  );
}

function job(changes: Partial<Job>): Job {
  return {
    id: "j1",
    kind: "tracking",
    dataset: "ds",
    state: "running",
    total_tasks: 11,
    done_tasks: 5,
    produced: 0,
    skipped: 0,
    quarantined: 0,
    cancel_requested: false,
    error: null,
    created_at: NOW,
    finalizing: false,
    ...changes,
  };
}

describe("canTrackFrom", () => {
  it("is so on a frame the object holds a box on", () => {
    expect(
      canTrackFrom(
        entityWith((entity) => [box(entity, 3)]),
        3,
      ),
    ).toBe(true);
  });

  it("is so on a frame the object holds a mask on", () => {
    expect(
      canTrackFrom(
        entityWith((entity) => [mask(entity, 2)]),
        2,
      ),
    ).toBe(true);
  });

  it("reads the frame from the annotation's data when its interface says none", () => {
    expect(
      canTrackFrom(
        entityWith((entity) => [box(entity, 4, false)]),
        4,
      ),
    ).toBe(true);
  });

  it("is not on a frame the object is not drawn on", () => {
    expect(
      canTrackFrom(
        entityWith((entity) => [box(entity, 3)]),
        5,
      ),
    ).toBe(false);
  });

  it("is not for an object with nothing drawn", () => {
    expect(
      canTrackFrom(
        entityWith(() => []),
        0,
      ),
    ).toBe(false);
  });
});

describe("trackingModel", () => {
  it("is the model chosen for the video tools when the inference serves it for tracking", () => {
    expect(trackingModel("sam-small-video", ["sam-tiny-video", "sam-small-video"])).toBe(
      "sam-small-video",
    );
  });

  it("is the first served for tracking when the one chosen is not", () => {
    expect(trackingModel("sam-image", ["sam-tiny-video"])).toBe("sam-tiny-video");
  });

  it("is the one chosen when the inference cannot say what it serves", () => {
    expect(trackingModel("sam-tiny-video", undefined)).toBe("sam-tiny-video");
  });

  it("is none when nothing is chosen nor served", () => {
    expect(trackingModel(undefined, [])).toBeNull();
  });
});

describe("trackingBlocker", () => {
  const free = { available: true, model: "sam", unsaved: false, lastFrame: false };

  it("is none when a worker and a model are there, nothing is unsaved, and frames follow", () => {
    expect(trackingBlocker(free)).toBeNull();
  });

  it("asks for a worker first, then a model", () => {
    expect(trackingBlocker({ ...free, available: false, model: null })).toMatch(/No worker/);
    expect(trackingBlocker({ ...free, model: null })).toMatch(/no tracking model/);
  });

  it("asks to save first: the job reads the video as it is saved", () => {
    expect(trackingBlocker({ ...free, unsaved: true })).toMatch(/Save your changes first/);
  });

  it("has nothing to follow on the video's last frame", () => {
    expect(trackingBlocker({ ...free, lastFrame: true })).toMatch(/last frame/);
  });
});

describe("showTrackedBlocker", () => {
  const free = { unsaved: false, session: null };

  it("lets the masks be shown when reading the record again drops nothing", () => {
    expect(showTrackedBlocker(free)).toBeNull();
  });

  it("asks for a save first, which reading the record again would drop", () => {
    expect(showTrackedBlocker({ ...free, unsaved: true })).toBe(
      "Save your changes first, then show them.",
    );
  });

  it("gives the session's own reason: leaving the drawing tool would end it", () => {
    // A mask tracking session holds its masks unsaved until its form is confirmed.
    const session = "Finish or cancel the mask tracking session first";

    expect(showTrackedBlocker({ ...free, session })).toBe(`${session}.`);
  });

  it("names what is unsaved before a session", () => {
    expect(
      showTrackedBlocker({
        unsaved: true,
        session: "Finish or cancel the tracking session first",
      }),
    ).toBe("Save your changes first, then show them.");
  });
});

describe("trackingParams", () => {
  it("names the object to follow, its video and the frame it starts from", () => {
    expect(trackingParams("sam", "record-1", "car", 3)).toEqual({
      model: "sam",
      objects: [{ record_id: "record-1", entity_id: "car", frame_index: 3 }],
    });
  });

  it("asks for what the job proposes when it is chosen", () => {
    expect(trackingParams("sam", "record-1", "car", 3, "boxes")).toMatchObject({ output: "boxes" });
  });

  it("asks for nothing a worker older than the choice would refuse when none is chosen", () => {
    expect(trackingParams("sam", "record-1", "car", 3)).not.toHaveProperty("output");
  });
});

describe("what the job proposes", () => {
  it("reads a choice back from the card's list, masks for anything else", () => {
    expect(trackingOutput("both")).toBe("both");
    expect(trackingOutput("box")).toBe("masks");
  });

  it("is said before the job is launched", () => {
    expect(trackingHint("sam", "masks")).toBe(
      "From this frame to the video's end, with sam. The masks arrive pending review.",
    );
    expect(trackingHint("sam", "boxes")).toMatch(/The boxes arrive pending review\.$/);
    expect(trackingHint("sam", "both")).toMatch(
      /The masks and their boxes arrive pending review\.$/,
    );
  });

  it("names the button that shows what the job wrote", () => {
    expect(showTrackedLabel("masks")).toBe("Show the masks");
    expect(showTrackedLabel("boxes")).toBe("Show the boxes");
    expect(showTrackedLabel("both")).toBe("Show the masks and boxes");
  });
});

describe("trackingSummary", () => {
  it("counts frames while the job runs", () => {
    expect(trackingSummary(job({}))).toBe("Tracking: 5 / 11 frames");
  });

  it("waits for a worker before one takes the job", () => {
    expect(trackingSummary(job({ state: "planning" }))).toBe("Waiting for a worker…");
  });

  it("says on how many frames the object got a mask", () => {
    expect(trackingSummary(job({ state: "done", produced: 11 }))).toBe(
      "Tracked: a mask on 11 frames",
    );
  });

  it("says what the job proposed on each frame", () => {
    const done = job({ state: "done", produced: 1 });

    expect(trackingSummary(done, "boxes")).toBe("Tracked: a box on 1 frame");
    expect(trackingSummary(done, "both")).toBe("Tracked: a mask and its box on 1 frame");
  });

  it("says when the object was lost at once", () => {
    expect(trackingSummary(job({ state: "done", produced: 0 }))).toBe(
      "Tracked: the object was lost on the next frame",
    );
  });

  it("says a cancellation and a failure apart", () => {
    expect(trackingSummary(job({ state: "cancelled" }))).toBe("Tracking cancelled");
    expect(trackingSummary(job({ state: "error" }))).toBe("Tracking failed");
  });

  it("says a cancellation asked for until the job stops", () => {
    expect(trackingSummary(job({ cancel_requested: true }))).toBe("Cancelling…");
  });

  it("says a video it could not track apart from an object lost", () => {
    expect(trackingSummary(job({ state: "done", produced: 0, quarantined: 1 }))).toMatch(
      /^Could not track the video/,
    );
    expect(trackingSummary(job({ state: "done", produced: 4, quarantined: 1 }))).toMatch(
      /^Tracked: a mask on 4 frames; a video could not be tracked/,
    );
  });
});
