/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildTrackletIdByChildId } from "$lib/stores/trackEditing";
import { Annotation, BaseSchema, BBox, Entity, Tracklet, WorkspaceType } from "$lib/types/dataset";

const mocks = vi.hoisted(() => ({
  annotations: { value: [] as unknown[] },
  entities: { value: [] as unknown[] },
  trackletIdByChildId: { value: new Map<string, string>() },
  currentFrameIndex: { value: 0 },
  editTrack: vi.fn(),
  exitEditMode: vi.fn(),
  isTrackEditing: vi.fn(() => false),
  deleteEntity: vi.fn(),
  onDeleteTrackItemClick: vi.fn(),
  clearHighlighting: vi.fn(),
  addKeyItemToTracklet: vi.fn(() => true),
  splitTrackletAfter: vi.fn(() => true),
}));

vi.mock("$lib/stores/workspaceStores.svelte", () => ({
  annotations: mocks.annotations,
  entities: mocks.entities,
  trackletIdByChildId: mocks.trackletIdByChildId,
  current_itemBBoxes: { value: [] },
  current_itemKeypoints: { value: [] },
  mediaViews: { value: {} },
}));
vi.mock("$lib/stores/videoStores.svelte", () => ({ currentFrameIndex: mocks.currentFrameIndex }));
vi.mock("$lib/utils/editMode", () => ({
  editTrack: mocks.editTrack,
  exitEditMode: mocks.exitEditMode,
  isTrackEditing: mocks.isTrackEditing,
}));
vi.mock("$lib/utils/entityDeletion", () => ({
  deleteEntity: mocks.deleteEntity,
  onDeleteTrackItemClick: mocks.onDeleteTrackItemClick,
}));
vi.mock("$lib/utils/highlightOperations", () => ({ clearHighlighting: mocks.clearHighlighting }));
vi.mock("$lib/utils/trackletOperations", () => ({
  addKeyItemToTracklet: mocks.addKeyItemToTracklet,
  splitTrackletAfter: mocks.splitTrackletAfter,
}));
vi.mock("$lib/utils/entityLookupUtils", () => ({
  tryGetTopEntity: (annotation: Annotation) =>
    (mocks.entities.value as Entity[]).find((entity) => entity.id === annotation.data.entity_id) ??
    null,
}));

const NOW = "2026-10-17T00:00:00+00:00";

function makeEntity(id: string): Entity {
  const entity = new Entity({
    id,
    table_info: { name: "entities", group: "entities", base_schema: BaseSchema.Entity },
    created_at: NOW,
    updated_at: NOW,
    data: { item_id: "item-1", parent_id: "" },
  });
  entity.ui.childs = [];
  return entity;
}

function makeBBox(id: string, entity: Entity, frame: number, trackletId: string): BBox {
  const bbox = new BBox({
    id,
    table_info: { name: "bboxes", group: "annotations", base_schema: BaseSchema.BBox },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      entity_id: entity.id,
      source_type: "ground_truth",
      source_name: "Pixano",
      source_metadata: "{}",
      view_name: "camera",
      inference_metadata: {},
      tracklet_id: trackletId,
      entity_dynamic_state_id: "",
      frame_id: `camera-frame-${frame}`,
      frame_index: frame,
      confidence: 1,
      coords: [0.1, 0.1, 0.2, 0.2],
      format: "xywh",
      is_normalized: true,
    },
  });
  bbox.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: false, highlighted: "all" },
    frame_index: frame,
    top_entities: [entity],
  };
  return bbox;
}

function makeTracklet(id: string, entity: Entity, frames: number[]): Tracklet {
  const childs = frames.map((frame) => makeBBox(`${id}-kf${frame}`, entity, frame, id));
  const tracklet = new Tracklet({
    id,
    table_info: { name: "tracklets", group: "annotations", base_schema: BaseSchema.Tracklet },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      entity_id: entity.id,
      source_type: "ground_truth",
      source_name: "Pixano",
      source_metadata: "{}",
      view_name: "camera",
      inference_metadata: {},
      start_frame: frames[0],
      end_frame: frames[frames.length - 1],
      start_timestamp: -1,
      end_timestamp: -1,
    },
  });
  tracklet.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: false, highlighted: "all" },
    childs,
    top_entities: [entity],
  };
  entity.ui.childs = [...(entity.ui.childs ?? []), tracklet, ...childs];
  return tracklet;
}

function useWorld(entities: Entity[], tracklets: Tracklet[], frame: number) {
  mocks.entities.value = entities;
  mocks.annotations.value = [...tracklets, ...tracklets.flatMap((tracklet) => tracklet.ui.childs)];
  mocks.trackletIdByChildId.value = buildTrackletIdByChildId(tracklets);
  mocks.currentFrameIndex.value = frame;
}

/** An interpolated box as displayed: a copy keyed `start::frame`, pointing to its start. */
function ghostOf(start: BBox, frame: number): BBox {
  const ghost = makeBBox(
    `${start.id}::${frame}`,
    start.ui.top_entities[0],
    frame,
    start.data.tracklet_id,
  );
  ghost.ui.startRef = start;
  return ghost;
}

describe("videoBoxActions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("offers a keyframe, a split and the object's deletion on an interpolated frame", async () => {
    const { videoBoxActions } = await import("$lib/utils/boxActions");
    const car = makeEntity("car");
    const track = makeTracklet("t1", car, [0, 10, 20]);
    useWorld([car], [track], 5);

    const actions = videoBoxActions(ghostOf(track.ui.childs[0] as BBox, 5));

    expect(actions.map((action) => action.id)).toEqual([
      "add-keyframe",
      "split-track",
      "delete-track",
    ]);
    expect(actions[2].label).toBe("Delete the object");
    expect(actions[2].destructive).toBe(true);

    actions[0].run();
    expect(mocks.addKeyItemToTracklet).toHaveBeenCalledWith(track, car, {}, [], [], 5);
    expect(mocks.editTrack).toHaveBeenCalledWith("t1", { reveal: false });
    actions[1].run();
    expect(mocks.splitTrackletAfter).toHaveBeenCalledWith(track, car, 5, {});
  });

  it("removes a keyframe only while two others remain", async () => {
    const { videoBoxActions } = await import("$lib/utils/boxActions");
    const car = makeEntity("car");
    const track = makeTracklet("t1", car, [0, 10, 20]);
    useWorld([car], [track], 10);

    const actions = videoBoxActions(track.ui.childs[1] as BBox);
    expect(actions.map((action) => action.id)).toEqual([
      "remove-keyframe",
      "split-track",
      "delete-track",
    ]);
    actions[0].run();
    expect(mocks.onDeleteTrackItemClick).toHaveBeenCalledWith(track, 10);

    const bus = makeEntity("bus");
    const short = makeTracklet("t2", bus, [0, 20]);
    useWorld([bus], [short], 20);
    expect(videoBoxActions(short.ui.childs[1] as BBox).map((action) => action.id)).toEqual([
      "delete-track",
    ]);
  });

  it("deletes only the track when the object has another one, and drops a deleted object's focus", async () => {
    const { videoBoxActions } = await import("$lib/utils/boxActions");
    const car = makeEntity("car");
    const first = makeTracklet("t1", car, [0, 10]);
    const second = makeTracklet("t2", car, [15, 20]);
    useWorld([car], [first, second], 5);

    const deleteTrack = videoBoxActions(ghostOf(first.ui.childs[0] as BBox, 5)).at(-1);
    expect(deleteTrack.label).toBe("Delete the track");

    mocks.isTrackEditing.mockReturnValue(true);
    mocks.deleteEntity.mockImplementation(() => {
      mocks.entities.value = [];
    });
    deleteTrack.run();
    expect(mocks.exitEditMode).toHaveBeenCalled();
    expect(mocks.deleteEntity).toHaveBeenCalledWith(car, first);
    expect(mocks.clearHighlighting).toHaveBeenCalled();
  });

  it("offers to delete a box outside every track", async () => {
    const { videoBoxActions, imageBoxActions } = await import("$lib/utils/boxActions");
    const sign = makeEntity("sign");
    const box = makeBBox("box-1", sign, 3, "");
    mocks.entities.value = [sign];
    mocks.annotations.value = [box];
    mocks.trackletIdByChildId.value = new Map();

    const actions = videoBoxActions(box);
    expect(actions.map((action) => action.id)).toEqual(["delete-box"]);
    expect(imageBoxActions(box).map((action) => action.id)).toEqual(["delete-box"]);
    actions[0].run();
    expect(mocks.deleteEntity).toHaveBeenCalledWith(sign, box);
  });
});
