/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import type {
  BBox3DRow,
  BBoxRow,
  EntityRow,
} from "$lib/api/annotations.js";
import type { CalibratedImageResponse, PointCloudResponse } from "$lib/api/restTypes.js";
import { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import type {
  WidgetComponentProps,
  WidgetExtensionConfig,
} from "$lib/extensions/types.js";
import type { Dataset } from "$lib/types/dataset";
import { DatasetInfo } from "$lib/types/dataset";
import type { Component } from "svelte";

import type { DatasetGateway } from "../datasetGateway.js";
import { WorkspaceManager } from "../workspaceManager.svelte.js";

// ─── Fake gateway ───────────────────────────────────────────────────────────
// In-memory implementation of `DatasetGateway`. Each scenario builds one
// that returns exactly the rows the test cares about and asserts on
// which methods got called, with what arguments — no `vi.mock` of the
// HTTP layer is needed.

interface FakeGatewayState {
  dataset: Dataset;
  entities: EntityRow[];
  imagesByLogicalName: Map<string, CalibratedImageResponse>;
  pointCloudsByLogicalName: Map<string, PointCloudResponse>;
  bboxes: BBoxRow[];
  bboxes3d: BBox3DRow[];
}

function makeGateway(state: FakeGatewayState) {
  const calls = {
    getDataset: 0,
    listEntities: 0,
    loadImageByLogicalName: 0,
    listBBoxes: 0,
    loadPointCloudByLogicalName: 0,
    listBBox3Ds: 0,
  };
  const gateway: DatasetGateway = {
    getDataset: () => {
      calls.getDataset++;
      return Promise.resolve(state.dataset);
    },
    listEntities: () => {
      calls.listEntities++;
      return Promise.resolve(state.entities);
    },
    loadImageByLogicalName: (_, __, logicalName) => {
      calls.loadImageByLogicalName++;
      return Promise.resolve(state.imagesByLogicalName.get(logicalName) ?? null);
    },
    listBBoxes: () => {
      calls.listBBoxes++;
      return Promise.resolve(state.bboxes);
    },
    loadPointCloudByLogicalName: (_, __, logicalName) => {
      calls.loadPointCloudByLogicalName++;
      return Promise.resolve(state.pointCloudsByLogicalName.get(logicalName) ?? null);
    },
    listBBox3Ds: () => {
      calls.listBBox3Ds++;
      return Promise.resolve(state.bboxes3d);
    },
    createEntity: () => Promise.resolve({}),
    deleteEntity: () => Promise.resolve(),
    createAnnotation: () => Promise.resolve({}),
    updateAnnotation: () => Promise.resolve({}),
    deleteAnnotation: () => Promise.resolve(),
  };
  return { gateway, calls };
}

// ─── Fake widget extensions ─────────────────────────────────────────────────
// Each test extension declares an `addRecordSeed` claiming the bases it
// understands, mirroring the real `ImageExtension` / `PointCloudExtension`
// shape with minimal fetches.

const stubComponent = (() => null) as unknown as Component<WidgetComponentProps>;

function makeRegistry(): WidgetRegistry {
  const registry = new WidgetRegistry();

  const imageExt: WidgetExtensionConfig = {
    name: "image",
    label: "Image",
    icon: "image",
    priority: 100,
    defaultLayout: { x: 0, y: 0, w: 3, h: 3 },
    component: stubComponent,
    addStorage: () => ({ activeToolId: "select" }),
    addRecordSeed: async ({ datasetId, recordId, viewName, viewDef, gateway }) => {
      if (viewDef.base !== "Image" && viewDef.base !== "CalibratedImage") return null;
      const image = await gateway.loadImageByLogicalName(datasetId, recordId, viewName);
      return {
        title: viewName,
        options: {
          datasetId,
          recordId,
          viewId: image?.id ?? "",
          viewName,
          imageWidth: image?.width ?? 0,
          imageHeight: image?.height ?? 0,
        },
        data: { imageUrl: image?.src },
        view: {
          id: image?.id ?? "",
          logicalName: viewName,
          width: image?.width ?? 0,
          height: image?.height ?? 0,
        },
      };
    },
  };

  const pointCloudExt: WidgetExtensionConfig = {
    name: "point-cloud",
    label: "Point Cloud",
    icon: "box",
    priority: 90,
    defaultLayout: { x: 0, y: 0, w: 3, h: 3 },
    component: stubComponent,
    addRecordSeed: async ({ datasetId, recordId, viewName, viewDef, gateway }) => {
      if (viewDef.base !== "PointCloud" && viewDef.base !== "CalibratedPointCloud") return null;
      const pointCloud = await gateway.loadPointCloudByLogicalName(datasetId, recordId, viewName);
      return {
        title: viewName,
        options: {},
        data: { pointCloudUrl: pointCloud?.src },
        view: { id: pointCloud?.id ?? "", logicalName: viewName, width: 0, height: 0 },
      };
    },
  };

  registry.register({ config: imageExt } as never);
  registry.register({ config: pointCloudExt } as never);
  return registry;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function makeDataset(views: Record<string, { base: string }>): Dataset {
  const info = new DatasetInfo({
    id: "ds-1",
    name: "Test",
    description: "",
    num_items: 1,
    size: "",
    preview: "",
    workspace: "image",
  });
  info.views = views;
  return {
    id: "ds-1",
    path: "",
    previews_path: "",
    media_dir: "",
    thumbnail: "",
    schema: {} as never,
    featureValues: {},
    info,
  };
}

const FIXED_VIEWPORT = { width: 1600, height: 900 };

describe("WorkspaceManager.toggleWidgetVisibility", () => {
  function findWidget(manager: WorkspaceManager, id: string) {
    return manager.widgets.find((w) => w.id === id);
  }

  it("toggles hidden from falsy to true", () => {
    const manager = new WorkspaceManager(makeRegistry());
    const { id } = manager.addWidget("image")!;

    manager.toggleWidgetVisibility(id);

    expect(findWidget(manager, id)?.hidden).toBe(true);
  });

  it("toggles hidden back to false on second call", () => {
    const manager = new WorkspaceManager(makeRegistry());
    const { id } = manager.addWidget("image")!;

    manager.toggleWidgetVisibility(id);
    manager.toggleWidgetVisibility(id);

    expect(findWidget(manager, id)?.hidden).toBe(false);
  });

  it("does nothing for an unknown id", () => {
    const manager = new WorkspaceManager(makeRegistry());
    const { id } = manager.addWidget("image")!;

    expect(() => manager.toggleWidgetVisibility("nonexistent")).not.toThrow();
    expect(findWidget(manager, id)?.hidden).toBeUndefined();
  });
});

describe("WorkspaceManager.selectRecordInDataset", () => {
  it("creates one widget per renderable view, in dataset order", async () => {
    const dataset = makeDataset({
      cam_front: { base: "Image" },
      lidar_top: { base: "PointCloud" },
      cam_back: { base: "Image" },
    });
    const { gateway } = makeGateway({
      dataset,
      entities: [],
      imagesByLogicalName: new Map([
        ["cam_front", { id: "img-front", src: "/f.png", width: 100, height: 50 } as CalibratedImageResponse],
        ["cam_back", { id: "img-back", src: "/b.png", width: 100, height: 50 } as CalibratedImageResponse],
      ]),
      pointCloudsByLogicalName: new Map([
        ["lidar_top", { id: "pc-top", src: "/lidar.pcd" } as PointCloudResponse],
      ]),
      bboxes: [],
      bboxes3d: [],
    });

    const manager = new WorkspaceManager(makeRegistry(), gateway);
    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);

    expect(manager.widgets.map((w) => w.title)).toEqual([
      "cam_front",
      "lidar_top",
      "cam_back",
    ]);
    expect(manager.widgets.map((w) => w.extensionName)).toEqual([
      "image",
      "point-cloud",
      "image",
    ]);
    expect(manager.datasetId).toBe("ds-1");
    expect(manager.recordId).toBe("rec-1");
  });

  it("seeds the shared collection with persisted bboxes (and attaches entities)", async () => {
    const dataset = makeDataset({ cam_front: { base: "Image" } });
    const entity: EntityRow = {
      id: "ent-1",
      record_id: "rec-1",
      // Other fields aren't read by the manager; the cast lets us keep the
      // fixture minimal.
    } as EntityRow;
    const bbox: BBoxRow = {
      id: "bb-1",
      record_id: "rec-1",
      view_id: "img-front",
      entity_id: "ent-1",
      coords: [0.1, 0.2, 0.3, 0.4],
      is_normalized: true,
    } as BBoxRow;

    const { gateway, calls } = makeGateway({
      dataset,
      entities: [entity],
      imagesByLogicalName: new Map([
        [
          "cam_front",
          { id: "img-front", src: "/f.png", width: 100, height: 50 } as CalibratedImageResponse,
        ],
      ]),
      pointCloudsByLogicalName: new Map(),
      bboxes: [bbox],
      bboxes3d: [],
    });

    const manager = new WorkspaceManager(makeRegistry(), gateway);
    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);

    expect(calls.listEntities).toBe(1);
    expect(calls.listBBoxes).toBe(1);

    expect(manager.annotations.byKind("bbox")).toHaveLength(1);
    expect(manager.annotations.find("bb-1")).toMatchObject({
      entityId: "ent-1",
      viewId: "img-front",
      persisted: true,
    });
    expect(manager.annotations.find("bb-1")!.entity).toStrictEqual(entity);
  });

  it("seeds 3D boxes (with entity attached) into the shared collection", async () => {
    const dataset = makeDataset({ lidar_top: { base: "PointCloud" } });
    const entity = { id: "ent-3d" } as EntityRow;
    const box3d: BBox3DRow = {
      id: "box-1",
      record_id: "rec-1",
      entity_id: "ent-3d",
      view_id: "",
      coords: [0, 0, 0, 1, 1, 1],
      format: "xyzwhd",
      rotation: [0, 0, 0],
      is_normalized: false,
    };

    const { gateway } = makeGateway({
      dataset,
      entities: [entity],
      imagesByLogicalName: new Map(),
      pointCloudsByLogicalName: new Map([
        ["lidar_top", { id: "pc-top", src: "/lidar.pcd" } as PointCloudResponse],
      ]),
      bboxes: [],
      bboxes3d: [box3d],
    });

    const manager = new WorkspaceManager(makeRegistry(), gateway);
    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);

    expect(manager.annotations.byKind("bbox3d")).toHaveLength(1);
    const annotation = manager.annotations.find("box-1");
    expect(annotation).toBeDefined();
    // Svelte 5 wraps session state in a $state proxy, so we compare by value
    // rather than reference identity.
    expect(annotation!.entity).toStrictEqual(entity);
  });

  it("throws when the dataset has no renderable views", async () => {
    const dataset = makeDataset({ misc: { base: "UnknownBase" } });
    const { gateway } = makeGateway({
      dataset,
      entities: [],
      imagesByLogicalName: new Map(),
      pointCloudsByLogicalName: new Map(),
      bboxes: [],
      bboxes3d: [],
    });

    const manager = new WorkspaceManager(makeRegistry(), gateway);
    await expect(
      manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT),
    ).rejects.toThrow("No renderable views");

    // datasetId/recordId are still set so any subsequent flushSave knows
    // which dataset to target — the error case shouldn't make the manager
    // pretend the user didn't select anything.
    expect(manager.datasetId).toBe("ds-1");
    expect(manager.recordId).toBe("rec-1");
  });

  it("kicks off getDataset and listEntities concurrently (no waterfall)", async () => {
    const dataset = makeDataset({ cam_front: { base: "Image" } });
    const order: string[] = [];

    let resolveDataset!: (d: Dataset) => void;
    let resolveEntities!: (e: EntityRow[]) => void;
    const datasetPromise = new Promise<Dataset>((r) => (resolveDataset = r));
    const entitiesPromise = new Promise<EntityRow[]>((r) => (resolveEntities = r));

    const gateway: DatasetGateway = {
      getDataset: () => {
        order.push("getDataset:start");
        return datasetPromise;
      },
      listEntities: () => {
        order.push("listEntities:start");
        return entitiesPromise;
      },
      loadImageByLogicalName: () =>
        Promise.resolve({ id: "img-1", src: "", width: 1, height: 1, f: null, c: null, distortion: null, extrinsic_matrix: null, ego_to_world: null } as CalibratedImageResponse),
      listBBoxes: () => Promise.resolve([]),
      loadPointCloudByLogicalName: () => Promise.resolve(null),
      listBBox3Ds: () => Promise.resolve([]),
      createEntity: () => Promise.resolve({}),
      createBBox: () => Promise.resolve({}),
      updateBBox: () => Promise.resolve({}),
      deleteBBox: () => Promise.resolve(),
      deleteEntity: () => Promise.resolve(),
      createBBox3D: () => Promise.resolve({}),
      updateBBox3D: () => Promise.resolve({}),
      deleteBBox3D: () => Promise.resolve(),
    };

    const manager = new WorkspaceManager(makeRegistry(), gateway);
    const done = manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);

    // Yield once so both fetches have a chance to start before either
    // resolves. If the manager waterfalled them, only `getDataset:start`
    // would be in `order` at this point.
    await Promise.resolve();
    expect(order).toEqual(["getDataset:start", "listEntities:start"]);

    resolveDataset(dataset);
    resolveEntities([]);
    await done;
  });
});
