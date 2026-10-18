/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { pinnableTimelineEntityIds, togglePinnedId } from "$lib/stores/timelinePinning";
import { BaseSchema, Entity, Tracklet, WorkspaceType } from "$lib/types/dataset";

const NOW = "2026-03-31T00:00:00+00:00";

function makeEntity(id: string, { tracked = true, hidden = false } = {}): Entity {
  const entity = new Entity({
    id,
    table_info: { name: "entities", group: "entities", base_schema: BaseSchema.Entity },
    created_at: NOW,
    updated_at: NOW,
    data: { item_id: "item-1", parent_id: "" },
  });
  const tracklet = new Tracklet({
    id: `${id}-track`,
    table_info: { name: "tracklets", group: "annotations", base_schema: BaseSchema.Tracklet },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      entity_id: id,
      source_type: "ground_truth",
      source_name: "Pixano",
      source_metadata: "{}",
      view_name: "camera",
      inference_metadata: {},
      start_frame: 0,
      end_frame: 4,
      start_timestamp: 0,
      end_timestamp: 4,
    },
  });
  tracklet.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: false, highlighted: "all" },
    childs: [],
    top_entities: [entity],
  };
  entity.ui.childs = tracked ? [tracklet] : [];
  entity.ui.displayControl = { ...entity.ui.displayControl, hidden };
  return entity;
}

describe("pinnableTimelineEntityIds", () => {
  it("keeps tracked, visible entities only", () => {
    const entities = [
      makeEntity("a"),
      makeEntity("b", { tracked: false }),
      makeEntity("c", { hidden: true }),
      makeEntity("d"),
    ];

    expect(pinnableTimelineEntityIds(entities)).toEqual(["a", "d"]);
  });
});

describe("togglePinnedId", () => {
  it("keeps every entity pinned by pin-all when one more is pinned", () => {
    const all = pinnableTimelineEntityIds(["a", "b", "c", "d", "e"].map((id) => makeEntity(id)));

    const pinned = togglePinnedId(all, "f");

    expect(pinned).toEqual(["f", "a", "b", "c", "d", "e"]);
  });

  it("unpins an entity already pinned", () => {
    expect(togglePinnedId(["a", "b", "c"], "b")).toEqual(["a", "c"]);
  });
});
