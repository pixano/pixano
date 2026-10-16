/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { BaseSchema, BBox, WorkspaceType } from "$lib/types/dataset";
import type { KeypointAnnotation } from "$lib/types/shapeTypes";
import {
  boxLinearInterpolation,
  interpolatedAnnotationId,
  keypointsLinearInterpolation,
} from "$lib/utils/interpolation";

const NOW = "2026-03-31T00:00:00+00:00";

function makeBBox(id: string, frameIndex: number, coords: number[]): BBox {
  const bbox = new BBox({
    id,
    table_info: {
      name: "bboxes",
      group: "annotations",
      base_schema: BaseSchema.BBox,
    },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      entity_id: "entity-1",
      source_type: "ground_truth",
      source_name: "Pixano",
      source_metadata: "{}",
      view_name: "camera",
      inference_metadata: {},
      tracklet_id: "track-1",
      entity_dynamic_state_id: "",
      frame_id: `camera-frame-${frameIndex}`,
      frame_index: frameIndex,
      confidence: 1,
      coords,
      format: "xywh",
      is_normalized: true,
    },
  });
  bbox.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: false, highlighted: "all" },
    frame_index: frameIndex,
    top_entities: [],
  };
  return bbox;
}

function makeKeypoints(id: string, frameIndex: number, x: number): KeypointAnnotation {
  return {
    id,
    template_id: "template",
    viewRef: { id: `camera-frame-${frameIndex}`, name: "camera" },
    graph: {
      vertices: [
        { x, y: 0.5 },
        { x: x + 0.1, y: 0.6 },
      ],
      edges: [[0, 1]],
    },
    vertexMetadata: [],
    ui: {
      frame_index: frameIndex,
      displayControl: { hidden: false, editing: false, highlighted: "all" },
    },
  };
}

describe("interpolatedAnnotationId", () => {
  it("joins the start annotation id and the frame index", () => {
    expect(interpolatedAnnotationId("bbox-0", 7)).toBe("bbox-0::7");
  });
});

describe("boxLinearInterpolation", () => {
  it("gives a ghost the same deterministic id on every derivation", () => {
    const boxes = [
      makeBBox("bbox-0", 0, [0, 0, 0.2, 0.2]),
      makeBBox("bbox-4", 4, [0.4, 0, 0.2, 0.2]),
    ];

    const first = boxLinearInterpolation(boxes, 2, "camera-frame-2");
    const second = boxLinearInterpolation(boxes, 2, "camera-frame-2");

    expect(first?.id).toBe("bbox-0::2");
    expect(second?.id).toBe(first?.id);
    expect(first?.data.coords[0]).toBeCloseTo(0.2);
    expect(first?.ui.startRef).toBe(boxes[0]);
  });
});

describe("keypointsLinearInterpolation", () => {
  const keypoints = [makeKeypoints("kpt-0", 0, 0), makeKeypoints("kpt-4", 4, 0.4)];

  it("gives a ghost the same deterministic id on every derivation", () => {
    const first = keypointsLinearInterpolation(keypoints, 2, "camera-frame-2");
    const second = keypointsLinearInterpolation(keypoints, 2, "camera-frame-2");

    expect(first?.id).toBe("kpt-0::2");
    expect(second?.id).toBe(first?.id);
    expect(first?.graph.vertices[0].x).toBeCloseTo(0.2);
    expect(first?.ui?.startRef).toBe(keypoints[0]);
  });

  it("returns the keyframe itself on its own frame", () => {
    expect(keypointsLinearInterpolation(keypoints, 4, "camera-frame-4")).toBe(keypoints[1]);
  });
});
