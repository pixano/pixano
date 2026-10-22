/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  cameraCoverage,
  cameraRowKey,
  cameraRowsDomId,
  canAddInView,
  keyframeScopeView,
  nextArming,
  nextRelinkSelection,
  resolveViewChoice,
  rowHeaderMeta,
  scopedLane,
  type RelinkChoice,
} from "../timelineCameras";
import { buildEntityTrackModel, EMPTY_LANE } from "../trackModel";
import { ToolType } from "$lib/types/tools";

const tracklet = (id: string, view: string, start: number, end: number, frames: number[]) => ({
  id,
  data: { entity_id: "person_1", view_name: view, start_frame: start, end_frame: end },
  ui: { childs: frames.map((frame_index) => ({ ui: { frame_index } })) },
});

describe("cameraCoverage", () => {
  it("lists the cameras with a track, in the record's order", () => {
    expect(cameraCoverage(["right", "left"], ["left", "right", "top"])).toEqual({
      present: ["left", "right"],
      total: 3,
      label: "2/3 views",
    });
    expect(cameraCoverage([], ["cam1"]).label).toBe("0/1 views");
  });

  it("ignores cameras the record does not have", () => {
    expect(cameraCoverage(["gone", "left"], ["left", "right"]).label).toBe("1/2 views");
  });
});

describe("keyframeScopeView", () => {
  const base = { viewCount: 3, viewFilter: null, expanded: false, activeCamera: "left" };

  it("follows the camera shown alone", () => {
    expect(keyframeScopeView({ ...base, viewFilter: "right" })).toBe("right");
  });

  it("follows the active camera on an expanded row", () => {
    expect(keyframeScopeView({ ...base, expanded: true })).toBe("left");
  });

  it("follows every camera on a collapsed row, or in a single-camera record", () => {
    expect(keyframeScopeView(base)).toBeNull();
    expect(keyframeScopeView({ ...base, viewCount: 1, expanded: true })).toBeNull();
  });
});

describe("resolveViewChoice", () => {
  it("keeps a camera of the record and falls back otherwise", () => {
    expect(resolveViewChoice("right", ["left", "right"], "left")).toBe("right");
    expect(resolveViewChoice("top", ["left", "right"], "left")).toBe("left");
    expect(resolveViewChoice(null, ["left"], null)).toBeNull();
  });
});

describe("scopedLane", () => {
  const model = buildEntityTrackModel(
    "person_1",
    [tracklet("a", "left", 0, 10, [0, 10]), tracklet("b", "right", 5, 20, [5, 20])],
    ["left", "right", "top"],
    () => "#f00",
  );

  it("gives a camera's lane, the merged lane, or an empty one", () => {
    expect(scopedLane(model, null)).toBe(model.union);
    expect(scopedLane(model, "right")).toBe(model.byView.get("right"));
    expect(scopedLane(model, "top")).toBe(EMPTY_LANE);
  });
});

describe("rowHeaderMeta", () => {
  const model = buildEntityTrackModel(
    "person_1",
    [tracklet("a", "left", 0, 10, [0, 5, 10]), tracklet("b", "right", 5, 20, [5, 20])],
    ["left", "right", "top"],
    () => "#f00",
  );
  const views = ["left", "right", "top"];

  it("counts the cameras that see the object in a multi-camera record", () => {
    expect(rowHeaderMeta(model, { viewOrder: views, viewFilter: null })).toBe("2/3 views");
  });

  it("counts the keyframes of the camera shown alone, or says it has none", () => {
    expect(rowHeaderMeta(model, { viewOrder: views, viewFilter: "left" })).toBe("3 kf");
    expect(rowHeaderMeta(model, { viewOrder: views, viewFilter: "top" })).toBe("—");
  });

  it("counts every keyframe in a single-camera record", () => {
    const single = buildEntityTrackModel(
      "person_1",
      [tracklet("a", "left", 0, 10, [0, 5, 10])],
      ["left"],
      () => "#f00",
    );
    expect(rowHeaderMeta(single, { viewOrder: ["left"], viewFilter: null })).toBe("3 kf");
  });
});

describe("nextRelinkSelection", () => {
  const choices: RelinkChoice[] = [
    { id: "new", kind: "new" },
    { id: "car", kind: "move" },
    { id: "truck", kind: "merge" },
    { id: "bus", kind: "forbidden" },
  ];

  it("preselects the armed object on the first run", () => {
    expect(nextRelinkSelection(choices, null, "car", true)).toBe("car");
    expect(nextRelinkSelection(choices, null, "truck", true)).toBe("truck");
  });

  it("falls back to new when the armed object cannot be picked", () => {
    expect(nextRelinkSelection(choices, null, "bus", true)).toBe("new");
    expect(nextRelinkSelection(choices, null, "gone", true)).toBe("new");
    expect(nextRelinkSelection(choices, null, null, true)).toBe("new");
  });

  it("keeps the user's choice while it is still offered", () => {
    expect(nextRelinkSelection(choices, "new", "car", false)).toBe("new");
    expect(nextRelinkSelection(choices, "truck", null, false)).toBe("truck");
  });

  it("moves away from a choice that left the list or became forbidden", () => {
    expect(nextRelinkSelection(choices, "gone", "car", false)).toBe("car");
    expect(nextRelinkSelection(choices, "bus", null, false)).toBe("new");
  });

  it("defaults to new on an empty list", () => {
    expect(nextRelinkSelection([], null, "car", true)).toBe("new");
  });
});

describe("nextArming", () => {
  const target = { entityId: "car", viewName: "right" };

  it("lasts while the box tool or its tracking session is on", () => {
    expect(
      nextArming(target, { type: "tool", toolType: ToolType.Rectangle, tracking: false }),
    ).toBe(target);
    expect(nextArming(target, { type: "tool", toolType: ToolType.Pan, tracking: true })).toBe(
      target,
    );
  });

  it("goes when the tool changes, the form closes or the record changes", () => {
    expect(
      nextArming(target, { type: "tool", toolType: ToolType.Pan, tracking: false }),
    ).toBeNull();
    expect(nextArming(target, { type: "save-closed", tracking: false })).toBeNull();
    expect(nextArming(target, { type: "record" })).toBeNull();
  });

  it("stays when the form is cancelled back into the tracking session", () => {
    expect(nextArming(target, { type: "save-closed", tracking: true })).toBe(target);
  });

  it("goes when the object is gone", () => {
    expect(nextArming(target, { type: "entities", ids: new Set(["car"]) })).toBe(target);
    expect(nextArming(target, { type: "entities", ids: new Set(["truck"]) })).toBeNull();
  });

  it("stays unarmed", () => {
    expect(
      nextArming(null, { type: "tool", toolType: ToolType.Rectangle, tracking: false }),
    ).toBeNull();
  });
});

describe("cameraRowKey", () => {
  it("never equals an object id, even one with a separator in it", () => {
    expect(cameraRowKey("car", "left")).not.toBe("car::left");
    expect(cameraRowKey("car", "left")).not.toBe(cameraRowKey("car::", "left"));
    expect(cameraRowKey("a", "b")).toBe(cameraRowKey("a", "b"));
  });
});

describe("cameraRowsDomId", () => {
  it("has no whitespace, so it is one IDREF", () => {
    expect(cameraRowsDomId("my car 1")).not.toMatch(/\s/);
  });
});

describe("canAddInView", () => {
  it("allows top-level objects only", () => {
    expect(canAddInView({ parentId: null })).toBe(true);
    expect(canAddInView({ parentId: "" })).toBe(true);
    expect(canAddInView({ parentId: "car" })).toBe(false);
    expect(canAddInView({ parentId: null, isConversation: true })).toBe(false);
  });
});
