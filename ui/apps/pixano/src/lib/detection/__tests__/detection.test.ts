/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  bboxToPixelBox,
  boxIou,
  boxNesting,
  buildDetectionRequest,
  collectExemplars,
  collectNegatives,
  DEFAULT_DETECTION_PARAMS,
  filterProposals,
  pixelBoxToNormalizedXywh,
  type DetectionImage,
  type DetectionRequestInput,
  type PixelBox,
} from "../detection";
import { BaseSchema, BBox, Entity, WorkspaceType } from "$lib/types/dataset";

const NOW = "2026-11-12T00:00:00";
const image: DetectionImage = { viewId: "view-1", viewName: "image", width: 200, height: 100 };

function entity(id: string, category?: string): Entity {
  return new Entity({
    id,
    table_info: { name: "objects", group: "entities", base_schema: BaseSchema.Entity },
    created_at: NOW,
    updated_at: NOW,
    data: { item_id: "record-1", parent_id: "", ...(category ? { category } : {}) },
  });
}

function bbox(
  id: string,
  entityId: string,
  coords: number[],
  options: { model?: boolean; accepted?: boolean; viewName?: string } = {},
): BBox {
  const box = new BBox({
    id,
    table_info: { name: "bboxes", group: "annotations", base_schema: BaseSchema.BBox },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "record-1",
      entity_id: entityId,
      source_type: options.model ? "model" : "ground_truth",
      source_name: options.model ? "sam3" : "Pixano",
      source_metadata: "{}",
      view_name: options.viewName ?? "image",
      view_id: "view-1",
      inference_metadata: {},
      tracklet_id: "",
      entity_dynamic_state_id: "",
      frame_id: "view-1",
      frame_index: -1,
      confidence: 1,
      coords,
      format: "xywh",
      is_normalized: true,
      ...(options.accepted ? { review_status: "accepted" } : {}),
    },
  });
  box.ui.datasetItemType = WorkspaceType.IMAGE;
  return box;
}

describe("box conversions", () => {
  it("turns a normalised xywh box into pixels and back", () => {
    const box = bbox("b", "e", [0.1, 0.2, 0.3, 0.4]);
    expect(bboxToPixelBox(box, 200, 100)).toEqual([20, 20, 80, 60]);
    expect(pixelBoxToNormalizedXywh([20, 20, 80, 60], 200, 100)).toEqual([0.1, 0.2, 0.3, 0.4]);
  });

  it("reads a pixel xyxy box as it is, and refuses a degenerate one", () => {
    const box = bbox("b", "e", [10, 20, 30, 40]);
    box.data = { ...box.data, format: "xyxy", is_normalized: false };
    expect(bboxToPixelBox(box, 200, 100)).toEqual([10, 20, 30, 40]);
    expect(bboxToPixelBox(bbox("z", "e", [0.1, 0.1, 0, 0.2]), 200, 100)).toBeNull();
  });

  it("measures overlap", () => {
    expect(boxIou([0, 0, 10, 10], [0, 0, 10, 10])).toBe(1);
    expect(boxIou([0, 0, 10, 10], [5, 0, 15, 10])).toBeCloseTo(1 / 3);
    expect(boxIou([0, 0, 10, 10], [20, 20, 30, 30])).toBe(0);
  });
});

describe("collectExemplars", () => {
  const entities = [
    entity("screw-1", "screw"),
    entity("screw-2", "Screw "),
    entity("nut-1", "nut"),
  ];

  it("takes the boxes of this view whose object is of the class, not a pending proposal", () => {
    const annotations = [
      bbox("a", "screw-1", [0.1, 0.1, 0.1, 0.1]),
      bbox("b", "screw-2", [0.5, 0.5, 0.1, 0.1]),
      bbox("c", "nut-1", [0.3, 0.3, 0.1, 0.1]),
      bbox("d", "screw-1", [0.7, 0.7, 0.1, 0.1], { model: true }),
      bbox("e", "screw-1", [0.2, 0.7, 0.1, 0.1], { model: true, accepted: true }),
      bbox("f", "screw-1", [0.2, 0.2, 0.1, 0.1], { viewName: "other" }),
    ];

    const exemplars = collectExemplars({
      annotations,
      entities,
      image,
      labelField: "category",
      className: "screw",
    });

    expect(exemplars).toEqual([
      [20, 10, 40, 20],
      [100, 50, 120, 60],
      [40, 70, 60, 80],
    ]);
  });

  it("needs a class when the dataset has a label field, and takes every box when it has none", () => {
    const annotations = [
      bbox("a", "screw-1", [0.1, 0.1, 0.1, 0.1]),
      bbox("c", "nut-1", [0.3, 0.3, 0.1, 0.1]),
    ];
    expect(
      collectExemplars({ annotations, entities, image, labelField: "category", className: " " }),
    ).toEqual([]);
    expect(
      collectExemplars({ annotations, entities, image, labelField: null, className: "" }),
    ).toHaveLength(2);
  });
});

describe("collectNegatives", () => {
  it("returns the proposals of this view no longer on it", () => {
    const proposals = [
      { bboxId: "kept", viewName: "image", box: [1, 1, 5, 5] as PixelBox },
      { bboxId: "rejected", viewName: "image", box: [10, 10, 20, 20] as PixelBox },
      { bboxId: "elsewhere", viewName: "other", box: [30, 30, 40, 40] as PixelBox },
    ];
    const annotations = [bbox("kept", "e", [0, 0, 0.1, 0.1], { model: true })];
    expect(collectNegatives(proposals, annotations, "image")).toEqual([[10, 10, 20, 20]]);
  });
});

describe("buildDetectionRequest", () => {
  const base: DetectionRequestInput = {
    model: "sam3",
    providerName: "pixano-inference@local",
    datasetId: "dataset-1",
    image,
    params: { ...DEFAULT_DETECTION_PARAMS, className: "screw", boxThreshold: 0.3 },
    exemplars: [[1, 2, 3, 4]],
    negatives: [[5, 6, 7, 8]],
    readsExemplars: true,
    readsNegatives: true,
  };

  it("sends the view, the class, the exemplars and the negatives", () => {
    expect(buildDetectionRequest(base)).toEqual({
      model: "sam3",
      provider_name: "pixano-inference@local",
      dataset_id: "dataset-1",
      view_id: "view-1",
      classes: ["screw"],
      box_threshold: 0.3,
      exemplar_boxes: [[1, 2, 3, 4]],
      negative_exemplar_boxes: [[5, 6, 7, 8]],
    });
  });

  it("leaves the text out of a visual prompt when asked", () => {
    const request = buildDetectionRequest({
      ...base,
      params: { ...base.params, classAsText: false },
    });
    expect(request?.classes).toBeNull();
    expect(request?.exemplar_boxes).toEqual([[1, 2, 3, 4]]);
  });

  it("sends no exemplar to a model that ignores them, and no negative without an exemplar", () => {
    const textOnly = buildDetectionRequest({
      ...base,
      readsExemplars: false,
      readsNegatives: false,
    });
    expect(textOnly?.classes).toEqual(["screw"]);
    expect(textOnly?.exemplar_boxes).toBeNull();
    expect(textOnly?.negative_exemplar_boxes).toBeNull();

    const noExemplar = buildDetectionRequest({ ...base, exemplars: [] });
    expect(noExemplar?.negative_exemplar_boxes).toBeNull();

    expect(
      buildDetectionRequest({ ...base, readsNegatives: false })?.negative_exemplar_boxes,
    ).toBeNull();
  });

  it("has nothing to ask without a class or an exemplar", () => {
    const params = { ...base.params, className: "" };
    expect(buildDetectionRequest({ ...base, params, exemplars: [] })).toBeNull();
    expect(buildDetectionRequest({ ...base, params, readsExemplars: false })).toBeNull();
    expect(buildDetectionRequest({ ...base, params })?.classes).toBeNull();
  });
});

describe("filterProposals", () => {
  it("drops boxes already on the image and repeats, clamps, and orders by score", () => {
    const output = {
      boxes: [
        [0, 0, 10, 10], // an exemplar found again
        [50, 50, 60, 60],
        [51, 50, 61, 60], // the same object, lower score
        [190, 90, 230, 130], // runs off the image
        [70, 70, 70, 80], // degenerate
      ],
      scores: [0.99, 0.6, 0.5, 0.8, 0.9],
      classes: ["screw", "screw", "screw", "screw", "screw"],
    };

    const { proposals, duplicates } = filterProposals(output, [[1, 0, 11, 10]], image);

    expect(proposals).toEqual([
      { box: [190, 90, 200, 100], score: 0.8 },
      { box: [50, 50, 60, 60], score: 0.6 },
    ]);
    expect(duplicates).toBe(2);
  });
});

describe("nested detections", () => {
  it("measures how much of the smaller box the larger holds", () => {
    expect(boxNesting([0, 0, 100, 100], [20, 20, 40, 40])).toBe(1);
    expect(boxNesting([0, 0, 10, 10], [5, 0, 15, 10])).toBe(0.5);
  });

  it("drops a part inside a box on the image, a group around one, and parts of one another", () => {
    // From a SAM 3 run on screws: a screw's head detected inside the screw (IoU 0.24).
    const output = {
      boxes: [
        [442, 558, 469, 583], // inside the stored screw
        [400, 500, 500, 620], // around it: a group
        [100, 100, 160, 160],
        [110, 110, 130, 130], // inside the previous proposal, lower score
        [300, 100, 340, 140], // a screw of its own
      ],
      scores: [0.9, 0.85, 0.8, 0.7, 0.6],
      classes: ["screw", "screw", "screw", "screw", "screw"],
    };

    const { proposals, duplicates } = filterProposals(output, [[426, 538, 478, 592]], {
      width: 720,
      height: 720,
    });

    expect(proposals.map((proposal) => proposal.box)).toEqual([
      [100, 100, 160, 160],
      [300, 100, 340, 140],
    ]);
    expect(duplicates).toBe(3);
  });
});
