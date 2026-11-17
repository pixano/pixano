/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  addDetectionExample,
  detectionSession,
  isDetectionExampleTool,
  openDetectionSetup,
  resetDetectionSession,
  runDetection,
  setDetectionApi,
  startAddingDetectionExamples,
  stopAddingDetectionExamples,
  updateDetectionParams,
} from "../detectionStore.svelte";
import { detectionExampleTool, panTool } from "$lib/tools";
import { BaseSchema, BBox, Entity, WorkspaceType, type FeaturesValues } from "$lib/types/dataset";
import { ImageTask, type DetectionTaskInput, type InferenceModel } from "$lib/types/inference";
import { ShapeType, type SaveRectangleShape } from "$lib/types/shapeTypes";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

const { stores, mocks } = vi.hoisted(() => ({
  stores: {
    annotations: { value: [] as unknown[] },
    entities: { value: [] as unknown[] },
    views: { value: {} },
    itemMetas: { value: { type: "image", item: { id: "record-1" } } },
    selectedTool: { value: null },
  },
  mocks: { saveTo: vi.fn(), commit: vi.fn(), detect: vi.fn() },
}));

vi.mock("$lib/stores/workspaceBaseStores.svelte", () => stores);
vi.mock("$lib/stores/workspaceStores.svelte", () => stores);
vi.mock("$lib/utils/saveItemUtils", () => ({ saveTo: mocks.saveTo }));
vi.mock("$lib/utils/workspaceRuntimeMutations", () => ({
  commitNormalizedWorkspaceRuntime: mocks.commit,
}));

const NOW = "2026-11-12T00:00:00";

const manifest = {
  workspaceType: WorkspaceType.IMAGE,
  tablesByName: {
    objects: {
      name: "objects",
      group: "entities",
      baseSchema: BaseSchema.Entity,
      fields: { category: { type: "str" } },
    },
    bboxes: { name: "bboxes", group: "annotations", baseSchema: BaseSchema.BBox, fields: {} },
  },
  tablesByGroup: {
    entities: ["objects"],
    annotations: ["bboxes"],
    views: ["image"],
    embeddings: [],
    item: [],
  },
  relations: {},
  baseSchemaToTable: {
    entities: { [BaseSchema.Entity]: "objects" },
    annotations: { [BaseSchema.BBox]: "bboxes" },
  },
} as unknown as WorkspaceManifest;

const sam3: InferenceModel = {
  name: "sam3",
  provider_name: "pixano-inference@local",
  task: ImageTask.DETECTION,
  interface: { capability: "detection", exemplars: true, negative_exemplars: true },
};
const gdino: InferenceModel = { ...sam3, name: "gdino", interface: { capability: "detection" } };

function screwBox(id: string, coords: number[]): BBox {
  const box = new BBox({
    id,
    table_info: { name: "bboxes", group: "annotations", base_schema: BaseSchema.BBox },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "record-1",
      entity_id: "screw-1",
      source_type: "ground_truth",
      source_name: "Pixano",
      source_metadata: "{}",
      view_name: "image",
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
    },
  });
  box.ui.datasetItemType = WorkspaceType.IMAGE;
  return box;
}

function respond(boxes: number[][], scores: number[]) {
  mocks.detect.mockResolvedValueOnce({
    data: { boxes, scores, classes: boxes.map(() => "screw") },
  });
}

describe("runDetection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setDetectionApi(mocks.detect);
    resetDetectionSession();
    stores.views.value = { image: { id: "view-1", data: { width: 200, height: 100 } } };
    stores.entities.value = [
      new Entity({
        id: "screw-1",
        table_info: { name: "objects", group: "entities", base_schema: BaseSchema.Entity },
        created_at: NOW,
        updated_at: NOW,
        data: { item_id: "record-1", parent_id: "", category: "screw" },
      }),
    ];
    stores.annotations.value = [screwBox("exemplar", [0.1, 0.1, 0.1, 0.1])];
    openDetectionSetup({ datasetId: "dataset-1", recordId: "record-1" }, "image");
    updateDetectionParams({ className: "screw", boxThreshold: 0.4 });
  });

  it("finds more like the boxed screws, stages the new ones, then avoids those rejected", async () => {
    const featureValues: FeaturesValues = { main: {}, objects: {} };
    respond(
      [
        [20, 10, 40, 20], // the exemplar, found again
        [100, 50, 120, 60],
        [150, 20, 170, 30],
      ],
      [0.95, 0.8, 0.7],
    );

    const result = await runDetection({ model: sam3, manifest, featureValues });

    expect(result).toEqual({ added: 2 });
    expect(mocks.detect).toHaveBeenCalledWith({
      model: "sam3",
      provider_name: "pixano-inference@local",
      dataset_id: "dataset-1",
      view_id: "view-1",
      classes: ["screw"],
      box_threshold: 0.4,
      exemplar_boxes: [[20, 10, 40, 20]],
      negative_exemplar_boxes: null,
    });
    const staged = mocks.saveTo.mock.calls.map(
      ([op, row]: [string, { table_info: { name: string } }]) => [op, row.table_info.name],
    );
    expect(staged).toEqual([
      ["add", "objects"],
      ["add", "objects"],
      ["add", "bboxes"],
      ["add", "bboxes"],
    ]);
    const [committed] = mocks.commit.mock.calls[0] as [BBox[]];
    const added = committed.slice(1);
    expect(added.map((bbox) => bbox.data.source_type)).toEqual(["model", "model"]);
    expect(added.map((bbox) => bbox.data.confidence)).toEqual([0.8, 0.7]);
    expect(added[0].data.coords).toEqual([0.5, 0.5, 0.1, 0.1]);
    expect(featureValues.objects.category?.values).toEqual(["screw"]);
    expect(detectionSession.value.lastRun).toMatchObject({ found: 3, added: 2, duplicates: 1 });

    // The person rejects the second proposal (a reject deletes it), keeps the first pending.
    stores.annotations.value = [stores.annotations.value[0], added[0]];
    mocks.saveTo.mockClear();
    // The model finds the rejected box again, and one new screw.
    respond(
      [
        [150, 20, 170, 30],
        [10, 70, 30, 80],
      ],
      [0.9, 0.6],
    );

    const again = await runDetection({ model: sam3, manifest, featureValues });

    const second = mocks.detect.mock.calls[1][0] as DetectionTaskInput;
    expect(second.exemplar_boxes).toEqual([[20, 10, 40, 20]]);
    expect(second.negative_exemplar_boxes).toEqual([[150, 20, 170, 30]]);
    expect(again).toEqual({ added: 1 });
    expect(detectionSession.value.lastRun).toMatchObject({ found: 2, added: 1, duplicates: 1 });
  });

  it("asks a model that ignores exemplars by text only", async () => {
    respond([], []);
    await runDetection({ model: gdino, manifest, featureValues: undefined });
    expect(mocks.detect.mock.calls[0][0]).toMatchObject({
      classes: ["screw"],
      exemplar_boxes: null,
    });
  });

  it("refuses to run with nothing to ask", async () => {
    updateDetectionParams({ className: "" });
    expect(await runDetection({ model: gdino, manifest, featureValues: undefined })).toBeNull();
    expect(mocks.detect).not.toHaveBeenCalled();
    expect(detectionSession.value.phase).toBe("error");
  });

  it("reports the server's refusal", async () => {
    mocks.detect.mockRejectedValueOnce(new Error("Model 'sam3' does not take exemplar boxes."));
    expect(await runDetection({ model: sam3, manifest, featureValues: undefined })).toBeNull();
    expect(detectionSession.value.error).toContain("exemplar");
    expect(mocks.saveTo).not.toHaveBeenCalled();
  });
});

describe("addDetectionExample", () => {
  const shape: SaveRectangleShape = {
    type: ShapeType.bbox,
    status: "saving",
    viewRef: { id: "view-1", name: "image" },
    itemId: "record-1",
    imageWidth: 200,
    imageHeight: 100,
    attrs: { x: 100, y: 50, width: 20, height: 10 },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    resetDetectionSession();
    stores.annotations.value = [];
    stores.entities.value = [];
    openDetectionSetup({ datasetId: "dataset-1", recordId: "record-1" }, "image");
  });

  it("saves a person's box whose object carries the panel's class", () => {
    updateDetectionParams({ className: " screw " });
    const featureValues: FeaturesValues = { main: {}, objects: {} };

    const bbox = addDetectionExample(shape, { manifest, featureValues });

    expect(bbox?.data.source_type).not.toBe("model");
    expect(bbox?.data.coords).toEqual([0.5, 0.5, 0.1, 0.1]);
    const [[, entity], [, box]] = mocks.saveTo.mock.calls as [string, Entity | BBox][];
    expect((entity as Entity).data.category).toBe("screw");
    expect(box).toBe(bbox);
    expect(featureValues.objects.category?.values).toEqual(["screw"]);
  });

  it("recognises the example tool by its fields: the real store holds a proxy, not the preset", () => {
    updateDetectionParams({ className: "screw" });
    startAddingDetectionExamples();
    stores.selectedTool.value = { ...(stores.selectedTool.value as object) };
    expect(stores.selectedTool.value).not.toBe(detectionExampleTool);
    expect(isDetectionExampleTool(stores.selectedTool.value as typeof panTool)).toBe(true);
    expect(isDetectionExampleTool(panTool)).toBe(false);
    stopAddingDetectionExamples();
    expect(stores.selectedTool.value).toBe(panTool);
  });

  it("saves nothing without a class", () => {
    updateDetectionParams({ className: "" });
    expect(addDetectionExample(shape, { manifest, featureValues: undefined })).toBeNull();
    expect(mocks.saveTo).not.toHaveBeenCalled();
  });
});
