/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  buildTrackletIdByChildId,
  markTrackEditing,
  pickEntityEditShape,
  PREVIEW_TABLE_NAME,
  shapeTopEntityId,
  shapeViewName,
  trackFrameActions,
  trackKeyframeFrames,
  trackletIdOfShape,
  trackletTopEntityId,
  type ShapeLike,
  type TrackLike,
} from "$lib/stores/trackEditing";

function track(
  id: string,
  frames: number[],
  entityId = "entity-1",
  viewName = "camera",
): TrackLike {
  return {
    id,
    data: {
      start_frame: frames[0],
      end_frame: frames[frames.length - 1],
      entity_id: entityId,
      view_name: viewName,
    },
    ui: { childs: frames.map((frame) => ({ id: `${id}-kf${frame}`, ui: { frame_index: frame } })) },
  };
}

/** A box as displayed: stored keyframe copy, or a ghost when `startRefId` is given. */
function box(
  id: string,
  options: { startRefId?: string; editing?: boolean; entityId?: string; view?: string } = {},
): ShapeLike {
  return {
    id,
    data: { entity_id: options.entityId ?? "entity-1", view_name: options.view ?? "camera" },
    ui: {
      displayControl: { hidden: false, editing: options.editing ?? false },
      ...(options.startRefId ? { startRef: { id: options.startRefId } } : {}),
    },
  };
}

/** Keypoints as displayed: no `data`, entity and view through references. */
function keypoints(id: string, startRefId?: string): ShapeLike {
  return {
    id,
    viewRef: { name: "camera" },
    entityRef: { id: "entity-1" },
    ui: {
      displayControl: { hidden: false, editing: false },
      ...(startRefId ? { startRef: { id: startRefId } } : {}),
    },
  };
}

describe("track lookup", () => {
  const tracks = [track("t1", [0, 10]), track("t2", [20, 30])];
  const map = buildTrackletIdByChildId(tracks);

  it("maps every keyframe to its track", () => {
    expect([...map.entries()]).toEqual([
      ["t1-kf0", "t1"],
      ["t1-kf10", "t1"],
      ["t2-kf20", "t2"],
      ["t2-kf30", "t2"],
    ]);
  });

  it("finds the track of a stored keyframe, a box ghost and a keypoint ghost", () => {
    expect(trackletIdOfShape(box("t1-kf10"), map)).toBe("t1");
    expect(trackletIdOfShape(box("t2-kf20::25", { startRefId: "t2-kf20" }), map)).toBe("t2");
    expect(trackletIdOfShape(keypoints("t1-kf0::4", "t1-kf0"), map)).toBe("t1");
    expect(trackletIdOfShape(box("untracked"), map)).toBeUndefined();
  });
});

describe("markTrackEditing", () => {
  const map = buildTrackletIdByChildId([track("t1", [0, 10]), track("t2", [0, 10])]);

  it("makes the edited track's shape editable on any frame, keyframe or ghost", () => {
    const keyframe = box("t1-kf0");
    const ghost = box("t1-kf0::5", { startRefId: "t1-kf0" });

    markTrackEditing([keyframe, ghost], "t1", map);

    expect(keyframe.ui?.displayControl.editing).toBe(true);
    expect(ghost.ui?.displayControl.editing).toBe(true);
  });

  it("turns off other tracks' shapes and leaves shapes outside tracks alone", () => {
    const other = box("t2-kf0", { editing: true });
    const otherControl = other.ui?.displayControl;
    const untracked = box("image-box", { editing: true });

    const shapes = [other, untracked];
    expect(markTrackEditing(shapes, "t1", map)).toBe(shapes);

    expect(other.ui?.displayControl.editing).toBe(false);
    // Display copies get a new display control instead of a write into a shared one.
    expect(other.ui?.displayControl).not.toBe(otherControl);
    expect(untracked.ui?.displayControl.editing).toBe(true);
  });

  it("makes no track shape editable when no track is in edit mode", () => {
    const keyframe = box("t1-kf10", { editing: true });
    markTrackEditing([keyframe], null, map);
    expect(keyframe.ui?.displayControl.editing).toBe(false);
  });
});

describe("entity and view of shapes", () => {
  it("reads the track's entity from its top entity, else from its data", () => {
    const withTop = track("t1", [0, 1]);
    withTop.ui.top_entities = [{ id: "parent" }];
    expect(trackletTopEntityId(withTop)).toBe("parent");
    expect(trackletTopEntityId(track("t2", [0, 1], "entity-2"))).toBe("entity-2");
  });

  it("reads boxes through data and keypoints through references", () => {
    expect(shapeTopEntityId(box("b", { entityId: "entity-9" }))).toBe("entity-9");
    expect(shapeViewName(box("b", { view: "left" }))).toBe("left");
    expect(shapeTopEntityId(keypoints("k"))).toBe("entity-1");
    expect(shapeViewName(keypoints("k"))).toBe("camera");
  });
});

describe("pickEntityEditShape", () => {
  const viewOrder = ["left", "right"];

  it("prefers the given view, then the view order, then the input order", () => {
    const leftBox = box("left-box", { view: "left" });
    const rightBox = box("right-box", { view: "right" });
    const leftKeypoints = { ...keypoints("left-kpt"), viewRef: { name: "left" } };

    expect(pickEntityEditShape([rightBox, leftKeypoints, leftBox], "entity-1", viewOrder)).toBe(
      leftKeypoints,
    );
    expect(pickEntityEditShape([leftBox, leftKeypoints], "entity-1", viewOrder)).toBe(leftBox);
    expect(pickEntityEditShape([leftBox, rightBox], "entity-1", viewOrder, "right")).toBe(rightBox);
  });

  it("skips other entities, previews and hidden shapes", () => {
    const other = box("other", { entityId: "entity-2", view: "left" });
    const preview = {
      ...box("preview", { view: "left" }),
      table_info: { name: PREVIEW_TABLE_NAME },
    };
    const hidden = box("hidden", { view: "left" });
    if (hidden.ui) hidden.ui.displayControl.hidden = true;

    expect(pickEntityEditShape([other, preview, hidden], "entity-1", viewOrder)).toBeUndefined();
  });
});

describe("track frame actions", () => {
  it("lists the distinct keyframe frames in order", () => {
    const tracklet = track("t", [10, 0, 10, 5]);
    expect(trackKeyframeFrames(tracklet)).toEqual([0, 5, 10]);
  });

  it("offers a keyframe on interpolated frames strictly inside the track", () => {
    const tracklet = track("t", [0, 10, 20]);
    expect(trackFrameActions(tracklet, 5)).toEqual({
      inTrack: true,
      isKeyframe: false,
      canAddKeyframe: true,
      canRemoveKeyframe: false,
      canSplit: true,
    });
    expect(trackFrameActions(tracklet, 0).canAddKeyframe).toBe(false);
    expect(trackFrameActions(tracklet, 25).inTrack).toBe(false);
  });

  it("removes a keyframe only when two others remain", () => {
    expect(trackFrameActions(track("t", [0, 10, 20]), 10).canRemoveKeyframe).toBe(true);
    expect(trackFrameActions(track("t", [0, 20]), 20).canRemoveKeyframe).toBe(false);
  });

  it("splits from the first frame up to the one before the last", () => {
    const tracklet = track("t", [0, 10]);
    expect(trackFrameActions(tracklet, 0).canSplit).toBe(true);
    expect(trackFrameActions(tracklet, 9).canSplit).toBe(true);
    expect(trackFrameActions(tracklet, 10).canSplit).toBe(false);
  });
});
