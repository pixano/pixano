/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { BaseSchema, BBox, Entity } from "$lib/types/dataset";
import { defineTooltip } from "$lib/utils/annotationMapping";

const NOW = "2026-11-19T00:00:00+00:00";

const car = new Entity({
  id: "car",
  table_info: { name: "entities", group: "entities", base_schema: BaseSchema.Entity },
  created_at: NOW,
  updated_at: NOW,
  data: { item_id: "record-1", parent_id: "", category: "car" },
});

function box(confidence: number, source: { type: string; name: string }): BBox {
  return new BBox({
    id: "box",
    table_info: { name: "bboxes", group: "annotations", base_schema: BaseSchema.BBox },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "record-1",
      entity_id: car.id,
      source_type: source.type,
      source_name: source.name,
      source_metadata: "{}",
      view_name: "video",
      inference_metadata: {},
      tracklet_id: "",
      entity_dynamic_state_id: "",
      frame_id: "frame-1",
      frame_index: 1,
      confidence,
      coords: [0.1, 0.2, 0.3, 0.4],
      format: "xywh",
      is_normalized: true,
    },
  });
}

const MODEL = { type: "model", name: "detection" };

describe("defineTooltip", () => {
  it("names a detected box's object, then its score", () => {
    expect(defineTooltip(box(0.871, MODEL), car)).toBe("car 0.87");
  });

  it("shows no score for a box no score came with, as the schema stores it", () => {
    // A box drawn around a tracked mask: the tracking model answers no score.
    expect(defineTooltip(box(-1, { type: "model", name: "tracking" }), car)).toBe("car");
  });

  it("shows no score of zero", () => {
    expect(defineTooltip(box(0, MODEL), car)).toBe("car");
  });

  it("shows no score on a ground truth's box", () => {
    expect(defineTooltip(box(1, { type: "ground_truth", name: "coco" }), car)).toBe("car");
  });
});
