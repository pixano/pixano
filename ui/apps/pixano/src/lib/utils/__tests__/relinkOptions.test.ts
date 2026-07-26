/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildRelinkOptions } from "../relinkOptions";
import { BaseSchema, type Annotation, type Entity, type Reference } from "$lib/types/dataset";

const VIEW: Reference = { id: "view_0", name: "image" };

interface FakeAnnotation {
  id: string;
  is_type: (type: BaseSchema) => boolean;
  table_info: { base_schema: BaseSchema };
  data: Record<string, unknown>;
  ui: Record<string, unknown>;
}

function fakeAnnotation(
  baseSchema: BaseSchema,
  data: Record<string, unknown> = {},
  ui: Record<string, unknown> = {},
): FakeAnnotation {
  return {
    id: (data.id as string) ?? `ann_${Math.abs(JSON.stringify(data).length)}`,
    is_type: (type: BaseSchema) => type === baseSchema,
    table_info: { base_schema: baseSchema },
    data,
    ui,
  };
}

function fakeEntity(id: string, childs: FakeAnnotation[] = [], parentId = ""): Entity {
  return {
    id,
    data: { parent_id: parentId, name: `Object ${id}` },
    is_conversation: false,
    ui: { childs },
  } as unknown as Entity;
}

const context = (entities: Entity[], overrides: Record<string, unknown> = {}) => ({
  entities,
  baseSchema: BaseSchema.BBox,
  viewRef: VIEW,
  track: null,
  currentFrameIndex: 0,
  ...overrides,
});

describe("buildRelinkOptions (image mode)", () => {
  it("always lists 'create new' first", () => {
    const options = buildRelinkOptions(context([]));
    expect(options[0]).toMatchObject({ id: "new", kind: "new" });
  });

  it("omits hard-forbidden entities (sub-entities and conversations)", () => {
    const sub = fakeEntity("sub", [], "some_parent");
    const convo = fakeEntity("convo");
    Object.defineProperty(convo, "is_conversation", { get: () => true });
    const options = buildRelinkOptions(context([sub, convo]));
    expect(options.map((o) => o.id)).toEqual(["new"]);
  });

  it("marks an entity with no overlap as move", () => {
    const plain = fakeEntity("e1");
    const options = buildRelinkOptions(context([plain]));
    expect(options[1]).toMatchObject({ id: "e1", kind: "move", conflicts: 0 });
  });

  it("marks same-kind-same-view collisions via conflicts (still move without tracklet overlap)", () => {
    const clashing = fakeEntity("e2", [
      fakeAnnotation(BaseSchema.BBox, { frame_id: "view_0" }),
    ]);
    const options = buildRelinkOptions(context([clashing]));
    // No tracklet overlap → kind stays move even with same-kind annotations (image datasets
    // have no tracklets); conflicts are only forbidden when an overlapping tracklet exists.
    expect(options[1].kind).toBe("move");
  });
});

describe("buildRelinkOptions (video mode, tracklets)", () => {
  const tracklet = (id: string, start: number, end: number) =>
    fakeAnnotation(BaseSchema.Tracklet, { id, view_name: "image", start_frame: start, end_frame: end });

  it("merge when a tracklet overlaps the current frame and no same-kind conflict", () => {
    const withTrack = fakeEntity("e3", [tracklet("t1", 0, 10)]);
    const options = buildRelinkOptions(context([withTrack], { currentFrameIndex: 5 }));
    expect(options[1]).toMatchObject({ id: "e3", kind: "merge", targets: ["t1"] });
  });

  it("forbidden when a tracklet overlaps AND a same-kind annotation exists in the view", () => {
    const conflicted = fakeEntity("e4", [
      tracklet("t2", 0, 10),
      fakeAnnotation(BaseSchema.BBox, { frame_id: "view_0" }),
    ]);
    const options = buildRelinkOptions(context([conflicted], { currentFrameIndex: 5 }));
    expect(options[1]).toMatchObject({ id: "e4", kind: "forbidden", conflicts: 1 });
  });

  it("move when tracklets exist but none overlap the current frame", () => {
    const outOfRange = fakeEntity("e5", [tracklet("t3", 20, 30)]);
    const options = buildRelinkOptions(context([outOfRange], { currentFrameIndex: 5 }));
    expect(options[1]).toMatchObject({ id: "e5", kind: "move" });
  });

  it("omits the track's own top entity when saving a track edit", () => {
    const trackAnn = fakeAnnotation(BaseSchema.Tracklet, {
      id: "t_self",
      view_name: "image",
      start_frame: 0,
      end_frame: 10,
    });
    (trackAnn.ui as Record<string, unknown>).childs = [];
    const owner = fakeEntity("owner", [trackAnn]);
    const options = buildRelinkOptions(
      context([owner], { track: trackAnn as unknown as Annotation, trackTopEntityId: "owner" }),
    );
    expect(options.map((o) => o.id)).toEqual(["new"]);
  });
});
