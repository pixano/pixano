/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Component } from "svelte";
import { describe, expect, it } from "vitest";

import type { DatasetGateway } from "../datasetGateway.js";
import { DATASET_LAYOUT_VERSION } from "../datasetLayout.js";
import { planViewportLayouts } from "../layoutPlanner.js";
import { WorkspaceManager } from "../workspaceManager.svelte.js";
import { makeLayoutRepository } from "./fakeDatasetLayoutRepository.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { BBOX3D_RESOURCE } from "$lib/annotations/kinds/3d/bbox3d/bbox3dPayloadBuilder.js";
import type { BBox3DRow, BBoxRow, EntityRow } from "$lib/api/annotations.js";
import type { CalibratedImageResponse, PointCloudResponse } from "$lib/api/restTypes.js";
import type { WidgetComponentProps, WidgetExtensionConfig } from "$lib/extensions/types.js";
import { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import type { Dataset } from "$lib/types/dataset";
import { DatasetInfo } from "$lib/types/dataset";

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
    loadPointCloudByLogicalName: 0,
    /** Per-resource listing counts, keyed by the annotation table name. */
    listAnnotations: {} as Record<string, number>,
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
    loadPointCloudByLogicalName: (_, __, logicalName) => {
      calls.loadPointCloudByLogicalName++;
      return Promise.resolve(state.pointCloudsByLogicalName.get(logicalName) ?? null);
    },
    loadTextByLogicalName: () => Promise.resolve(null),
    listAnnotations: <TRow>(_datasetId: string, resource: string): Promise<TRow[]> => {
      calls.listAnnotations[resource] = (calls.listAnnotations[resource] ?? 0) + 1;
      if (resource === BBOX_RESOURCE) return Promise.resolve(state.bboxes as TRow[]);
      if (resource === BBOX3D_RESOURCE) return Promise.resolve(state.bboxes3d as TRow[]);
      return Promise.resolve([]);
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

describe("WorkspaceManager entity visibility", () => {
  it("defaults to all entities visible (null filter)", () => {
    const manager = new WorkspaceManager(makeRegistry());
    expect(manager.visibleEntityIds).toBeNull();
    expect(manager.isEntityVisible("any")).toBe(true);
  });

  it("toggleEntityVisible isolates a single entity", () => {
    const manager = new WorkspaceManager(makeRegistry());

    manager.toggleEntityVisible("e1");

    expect(manager.isEntityVisible("e1")).toBe(true);
    expect(manager.isEntityVisible("e2")).toBe(false);
    expect([...(manager.visibleEntityIds ?? [])]).toEqual(["e1"]);
  });

  it("toggling a different entity switches the isolation", () => {
    const manager = new WorkspaceManager(makeRegistry());

    manager.toggleEntityVisible("e1");
    manager.toggleEntityVisible("e2");

    expect(manager.isEntityVisible("e1")).toBe(false);
    expect(manager.isEntityVisible("e2")).toBe(true);
  });

  it("toggling the already-isolated entity returns to show-all", () => {
    const manager = new WorkspaceManager(makeRegistry());

    manager.toggleEntityVisible("e1");
    manager.toggleEntityVisible("e1");

    expect(manager.visibleEntityIds).toBeNull();
    expect(manager.isEntityVisible("anything")).toBe(true);
  });

  it("showAllEntities clears any isolation", () => {
    const manager = new WorkspaceManager(makeRegistry());

    manager.toggleEntityVisible("e1");
    manager.showAllEntities();

    expect(manager.visibleEntityIds).toBeNull();
    expect(manager.isEntityVisible("e2")).toBe(true);
  });

  it("hideAllEntities hides every entity", () => {
    const manager = new WorkspaceManager(makeRegistry());

    manager.hideAllEntities();

    expect(manager.visibleEntityIds?.size).toBe(0);
    expect(manager.isEntityVisible("e1")).toBe(false);
  });

  it("toggleAllEntitiesVisible hides everything when all entities are shown", () => {
    const manager = new WorkspaceManager(makeRegistry());

    manager.toggleAllEntitiesVisible();

    expect(manager.isEntityVisible("e1")).toBe(false);
  });

  it("toggleAllEntitiesVisible shows everything when an entity is isolated", () => {
    const manager = new WorkspaceManager(makeRegistry());

    manager.toggleEntityVisible("e1");
    manager.toggleAllEntitiesVisible();

    expect(manager.visibleEntityIds).toBeNull();
    expect(manager.isEntityVisible("e2")).toBe(true);
  });

  it("toggleAllEntitiesVisible returns to show-all after hiding everything", () => {
    const manager = new WorkspaceManager(makeRegistry());

    manager.toggleAllEntitiesVisible();
    manager.toggleAllEntitiesVisible();

    expect(manager.visibleEntityIds).toBeNull();
    expect(manager.isEntityVisible("e1")).toBe(true);
  });

  it("clears the selection when hiding all entities", () => {
    const manager = new WorkspaceManager(makeRegistry());
    manager.annotations.add({
      id: "b-eB",
      entityId: "eB",
      kind: "bbox",
      viewId: "v1",
      geometry: [0, 0, 1, 1],
      persisted: true,
    });
    manager.annotations.select("b-eB");

    manager.hideAllEntities();

    expect(manager.annotations.selectedId).toBeNull();
  });

  it("clears a selection that isolation has just hidden (no delete on an unseen box)", () => {
    const manager = new WorkspaceManager(makeRegistry());
    manager.annotations.add({
      id: "b-eB",
      entityId: "eB",
      kind: "bbox",
      viewId: "v1",
      geometry: [0, 0, 1, 1],
      persisted: true,
    });
    manager.annotations.select("b-eB");

    // Isolate a different entity → the selected box is now hidden.
    manager.toggleEntityVisible("eA");

    expect(manager.annotations.selectedId).toBeNull();
  });

  it("keeps a selection that stays visible after isolation", () => {
    const manager = new WorkspaceManager(makeRegistry());
    manager.annotations.add({
      id: "b-eA",
      entityId: "eA",
      kind: "bbox",
      viewId: "v1",
      geometry: [0, 0, 1, 1],
      persisted: true,
    });
    manager.annotations.select("b-eA");

    manager.toggleEntityVisible("eA");

    expect(manager.annotations.selectedId).toBe("b-eA");
  });

  it("keeps a draft selected even when its entity isn't in the visible set", () => {
    const manager = new WorkspaceManager(makeRegistry());
    manager.annotations.add({
      id: "draft",
      entityId: "",
      kind: "bbox",
      viewId: "v1",
      geometry: [0, 0, 1, 1],
      persisted: false,
    });
    manager.annotations.select("draft");

    manager.toggleEntityVisible("eA");

    expect(manager.annotations.selectedId).toBe("draft");
  });
});

describe("WorkspaceManager.deleteAnnotation", () => {
  it("queues a single backend delete for a persisted annotation and removes it", () => {
    const manager = new WorkspaceManager(makeRegistry());
    manager.annotations.add({
      id: "b1",
      entityId: "e1",
      kind: "bbox3d",
      viewId: "",
      geometry: { coords: [0, 0, 0, 1, 1, 1], format: "xyzwhd" },
      persisted: true,
    });

    manager.deleteAnnotation(manager.annotations.find("b1")!, "w1");

    expect(manager.annotations.find("b1")).toBeUndefined();
    // Only the annotation row; the orphan entity is pruned server-side.
    expect(manager.pendingMutations).toHaveLength(1);
    expect(manager.pendingMutations[0]).toMatchObject({
      op: "delete",
      resource: "bbox3ds",
      id: "b1",
    });
  });

  it("drops pending creates for an unsaved annotation instead of queueing a delete", () => {
    const manager = new WorkspaceManager(makeRegistry());
    manager.annotations.add({
      id: "draft",
      entityId: "",
      kind: "bbox3d",
      viewId: "",
      geometry: { coords: [0, 0, 0, 1, 1, 1], format: "xyzwhd" },
      persisted: false,
    });

    manager.deleteAnnotation(manager.annotations.find("draft")!, "w1");

    expect(manager.annotations.find("draft")).toBeUndefined();
    expect(manager.pendingMutations).toHaveLength(0);
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
        [
          "cam_front",
          { id: "img-front", src: "/f.png", width: 100, height: 50 } as CalibratedImageResponse,
        ],
        [
          "cam_back",
          { id: "img-back", src: "/b.png", width: 100, height: 50 } as CalibratedImageResponse,
        ],
      ]),
      pointCloudsByLogicalName: new Map([
        ["lidar_top", { id: "pc-top", src: "/lidar.pcd" } as PointCloudResponse],
      ]),
      bboxes: [],
      bboxes3d: [],
    });

    const manager = new WorkspaceManager(makeRegistry(), gateway);
    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);

    expect(manager.widgets.map((w) => w.title)).toEqual(["cam_front", "lidar_top", "cam_back"]);
    expect(manager.widgets.map((w) => w.extensionName)).toEqual(["image", "point-cloud", "image"]);
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
    expect(calls.listAnnotations[BBOX_RESOURCE]).toBe(1);

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

  it("refreshes the entity list after a successful flushSave", async () => {
    const dataset = makeDataset({ cam_front: { base: "Image" } });
    const state = {
      dataset,
      entities: [{ id: "ent-old", record_id: "rec-1" } as EntityRow],
      imagesByLogicalName: new Map([
        [
          "cam_front",
          { id: "img-front", src: "/f.png", width: 100, height: 50 } as CalibratedImageResponse,
        ],
      ]),
      pointCloudsByLogicalName: new Map(),
      bboxes: [],
      bboxes3d: [],
    };
    const { gateway, calls } = makeGateway(state);

    const manager = new WorkspaceManager(makeRegistry(), gateway);
    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    expect(manager.entities.map((e) => e.id)).toEqual(["ent-old"]);

    // Simulate the backend having created one entity and pruned the old one
    // during the flush; the post-save refetch should pick this up.
    state.entities = [{ id: "ent-new", record_id: "rec-1" } as EntityRow];
    manager.queueMutation({ op: "delete", resource: "bbox3ds", id: "x", widgetId: "w" });
    await manager.flushSave();

    expect(calls.listEntities).toBe(2); // once on load, once after save
    expect(manager.entities.map((e) => e.id)).toEqual(["ent-new"]);
  });

  it("drops the selection once a save succeeds, so editing handles retract", async () => {
    const dataset = makeDataset({ cam_front: { base: "Image" } });
    const { gateway } = makeGateway({
      dataset,
      entities: [],
      imagesByLogicalName: new Map([
        [
          "cam_front",
          { id: "img-front", src: "/f.png", width: 100, height: 50 } as CalibratedImageResponse,
        ],
      ]),
      pointCloudsByLogicalName: new Map(),
      bboxes: [],
      bboxes3d: [],
    });

    const manager = new WorkspaceManager(makeRegistry(), gateway);
    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    manager.annotations.add({
      id: "a1",
      entityId: "e1",
      kind: "bbox",
      viewId: "img-front",
      geometry: [0, 0, 0.1, 0.1],
      persisted: true,
    });
    manager.annotations.select("a1");

    manager.queueMutation({ op: "delete", resource: "bboxes", id: "a1", widgetId: "w" });
    await manager.flushSave();

    expect(manager.annotations.selectedId).toBeNull();
  });

  it("keeps the selection when the save failed, leaving the work as it was", async () => {
    const dataset = makeDataset({ cam_front: { base: "Image" } });
    const { gateway } = makeGateway({
      dataset,
      entities: [],
      imagesByLogicalName: new Map([
        [
          "cam_front",
          { id: "img-front", src: "/f.png", width: 100, height: 50 } as CalibratedImageResponse,
        ],
      ]),
      pointCloudsByLogicalName: new Map(),
      bboxes: [],
      bboxes3d: [],
    });
    // Make the flush fail: the annotation stays selected and still editable.
    gateway.deleteAnnotation = () => Promise.reject(new Error("backend down"));

    const manager = new WorkspaceManager(makeRegistry(), gateway);
    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    manager.annotations.add({
      id: "a1",
      entityId: "e1",
      kind: "bbox",
      viewId: "img-front",
      geometry: [0, 0, 0.1, 0.1],
      persisted: true,
    });
    manager.annotations.select("a1");

    manager.queueMutation({ op: "delete", resource: "bboxes", id: "a1", widgetId: "w" });
    await manager.flushSave();

    expect(manager.saveError).not.toBeNull();
    expect(manager.annotations.selectedId).toBe("a1");
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
    await expect(manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT)).rejects.toThrow(
      "No renderable views",
    );

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
        Promise.resolve({
          id: "img-1",
          src: "",
          width: 1,
          height: 1,
          f: null,
          c: null,
          distortion: null,
          extrinsic_matrix: null,
          ego_to_world: null,
        } as CalibratedImageResponse),
      loadPointCloudByLogicalName: () => Promise.resolve(null),
      loadTextByLogicalName: () => Promise.resolve(null),
      listAnnotations: () => Promise.resolve([]),
      createEntity: () => Promise.resolve({}),
      deleteEntity: () => Promise.resolve(),
      createAnnotation: () => Promise.resolve({}),
      updateAnnotation: () => Promise.resolve({}),
      deleteAnnotation: () => Promise.resolve(),
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

// ─── Per-dataset layout preference ───────────────────────────────────────────
// End-to-end through the manager: an arrangement made on one record is stored
// against the dataset and replayed when another of its records is opened.

describe("WorkspaceManager dataset layout preference", () => {
  function makeTwoViewGateway() {
    return makeGateway({
      dataset: makeDataset({ cam_front: { base: "Image" }, lidar_top: { base: "PointCloud" } }),
      entities: [],
      imagesByLogicalName: new Map([
        [
          "cam_front",
          { id: "img-front", src: "/f.png", width: 100, height: 50 } as CalibratedImageResponse,
        ],
      ]),
      pointCloudsByLogicalName: new Map([
        ["lidar_top", { id: "pc-top", src: "/lidar.pcd" } as PointCloudResponse],
      ]),
      bboxes: [],
      bboxes3d: [],
    });
  }

  it("keys record-seeded widgets by their dataset view", async () => {
    const { gateway } = makeTwoViewGateway();
    const manager = new WorkspaceManager(makeRegistry(), gateway, makeLayoutRepository());

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);

    expect(manager.widgets.map((w) => w.viewName)).toEqual(["cam_front", "lidar_top"]);
  });

  it("reuses on a later record the arrangement saved on an earlier one", async () => {
    const { gateway } = makeTwoViewGateway();
    const layouts = makeLayoutRepository();
    const manager = new WorkspaceManager(makeRegistry(), gateway, layouts);

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    // The user drags the lidar widget across the grid; the grid component then
    // asks the manager to remember the arrangement.
    manager.updateLayout(manager.widgets[1].id, { x: 0, y: 7, w: 12, h: 3 });
    manager.saveDatasetLayout();

    manager.clearWorkspace();
    await manager.selectRecordInDataset("ds-1", "rec-2", FIXED_VIEWPORT);

    expect(manager.widgets[1].layout).toEqual({ x: 0, y: 7, w: 12, h: 3 });
  });

  it("replays a hidden view as hidden on the next record", async () => {
    const { gateway } = makeTwoViewGateway();
    const layouts = makeLayoutRepository();
    const manager = new WorkspaceManager(makeRegistry(), gateway, layouts);

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    manager.toggleWidgetVisibility(manager.widgets[1].id);
    // The grid persists once its reflow has settled; stand in for it here.
    manager.saveDatasetLayout();

    manager.clearWorkspace();
    await manager.selectRecordInDataset("ds-1", "rec-2", FIXED_VIEWPORT);

    expect(manager.widgets.map((w) => w.hidden)).toEqual([false, true]);
  });

  it("keeps each dataset's arrangement to itself", async () => {
    const { gateway } = makeTwoViewGateway();
    const layouts = makeLayoutRepository();
    const manager = new WorkspaceManager(makeRegistry(), gateway, layouts);

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    const arranged = { x: 0, y: 7, w: 12, h: 3 };
    manager.updateLayout(manager.widgets[1].id, arranged);
    manager.saveDatasetLayout();

    manager.clearWorkspace();
    await manager.selectRecordInDataset("ds-2", "rec-1", FIXED_VIEWPORT);

    expect(manager.widgets[1].layout).not.toEqual(arranged);
  });

  it("does not save when no record is open, so clearing keeps the arrangement", async () => {
    const { gateway } = makeTwoViewGateway();
    const layouts = makeLayoutRepository();
    const manager = new WorkspaceManager(makeRegistry(), gateway, layouts);

    manager.saveDatasetLayout();

    expect(layouts.saved).toHaveLength(0);
  });

  it("does not overwrite the arrangement with an empty workspace", async () => {
    const { gateway } = makeTwoViewGateway();
    const layouts = makeLayoutRepository();
    const manager = new WorkspaceManager(makeRegistry(), gateway, layouts);

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    manager.saveDatasetLayout();
    // `clearWorkspace` keeps the session's dataset selection, so a save
    // triggered afterwards must not erase what was stored.
    manager.clearWorkspace();
    manager.saveDatasetLayout();

    expect(layouts.load("ds-1")?.views.cam_front).toBeDefined();
  });

  it("puts the widgets back where the record opened them", async () => {
    const { gateway } = makeTwoViewGateway();
    const layouts = makeLayoutRepository();
    const manager = new WorkspaceManager(makeRegistry(), gateway, layouts);

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    const opening = manager.widgets.map((w) => ({ ...w.layout }));

    manager.updateLayout(manager.widgets[1].id, { x: 0, y: 7, w: 12, h: 3 });
    manager.toggleWidgetVisibility(manager.widgets[0].id);
    manager.restoreOpeningLayout();

    expect(manager.widgets.map((w) => w.layout)).toEqual(opening);
    expect(manager.widgets.map((w) => w.hidden)).toEqual([false, false]);
  });

  it("tells the grid to re-apply the restored positions", async () => {
    const { gateway } = makeTwoViewGateway();
    const manager = new WorkspaceManager(makeRegistry(), gateway, makeLayoutRepository());

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    const before = manager.layoutRevision;
    manager.restoreOpeningLayout();

    expect(manager.layoutRevision).toBe(before + 1);
  });

  it("stores the restored arrangement, so screen and storage never disagree", async () => {
    const { gateway } = makeTwoViewGateway();
    const layouts = makeLayoutRepository();
    const manager = new WorkspaceManager(makeRegistry(), gateway, layouts);

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    const opening = { ...manager.widgets[1].layout };
    manager.updateLayout(manager.widgets[1].id, { x: 0, y: 7, w: 12, h: 3 });
    manager.saveDatasetLayout();

    manager.restoreOpeningLayout();

    expect(layouts.load("ds-1")?.views.lidar_top.layout).toEqual(opening);
  });

  it("does nothing before a record has loaded", () => {
    const { gateway } = makeTwoViewGateway();
    const layouts = makeLayoutRepository();
    const manager = new WorkspaceManager(makeRegistry(), gateway, layouts);

    expect(() => manager.restoreOpeningLayout()).not.toThrow();
    expect(layouts.saved).toHaveLength(0);
  });

  it("restores a view that was hidden when the record opened", async () => {
    const { gateway } = makeTwoViewGateway();
    // The dataset's stored arrangement hides the lidar, so the record opens with
    // it hidden — the state "Reset layout" has to be able to get back to.
    const layouts = makeLayoutRepository({
      "ds-1": {
        version: DATASET_LAYOUT_VERSION,
        views: {
          cam_front: { layout: { x: 0, y: 0, w: 12, h: 6 }, hidden: false },
          lidar_top: { layout: { x: 0, y: 6, w: 12, h: 6 }, hidden: true },
        },
      },
    });
    const manager = new WorkspaceManager(makeRegistry(), gateway, layouts);

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    expect(manager.widgets.map((w) => w.hidden)).toEqual([false, true]);

    manager.toggleWidgetVisibility(manager.widgets[1].id);
    manager.updateLayout(manager.widgets[0].id, { x: 3, y: 3, w: 6, h: 3 });
    manager.restoreOpeningLayout();

    expect(manager.widgets.map((w) => w.hidden)).toEqual([false, true]);
    expect(manager.widgets[0].layout).toMatchObject({ x: 0, y: 0, w: 12, h: 6 });
  });

  it("drops the opening arrangement when the workspace is cleared", async () => {
    const { gateway } = makeTwoViewGateway();
    const manager = new WorkspaceManager(makeRegistry(), gateway, makeLayoutRepository());

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    manager.clearWorkspace();

    // Nothing to restore onto, and nothing stale left describing the old record.
    const before = manager.layoutRevision;
    manager.restoreOpeningLayout();
    expect(manager.layoutRevision).toBe(before);
  });
});

// ─── Fit layout ──────────────────────────────────────────────────────────────

describe("WorkspaceManager.fitLayoutToViewport", () => {
  function makeTwoViewGateway() {
    return makeGateway({
      dataset: makeDataset({ cam_front: { base: "Image" }, lidar_top: { base: "PointCloud" } }),
      entities: [],
      imagesByLogicalName: new Map([
        [
          "cam_front",
          { id: "img-front", src: "/f.png", width: 100, height: 50 } as CalibratedImageResponse,
        ],
      ]),
      pointCloudsByLogicalName: new Map([
        ["lidar_top", { id: "pc-top", src: "/lidar.pcd" } as PointCloudResponse],
      ]),
      bboxes: [],
      bboxes3d: [],
    });
  }

  it("re-tiles every widget to the automatic placement for the viewport", async () => {
    const { gateway } = makeTwoViewGateway();
    const manager = new WorkspaceManager(makeRegistry(), gateway, makeLayoutRepository());

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    manager.updateLayout(manager.widgets[0].id, { x: 9, y: 40, w: 3, h: 3 });

    manager.fitLayoutToViewport(FIXED_VIEWPORT);

    expect(manager.widgets.map((w) => w.layout)).toEqual(
      planViewportLayouts(2, FIXED_VIEWPORT).map((layout) => expect.objectContaining(layout)),
    );
  });

  it("reveals hidden widgets, so nothing is left off-screen", async () => {
    const { gateway } = makeTwoViewGateway();
    const manager = new WorkspaceManager(makeRegistry(), gateway, makeLayoutRepository());

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    manager.toggleWidgetVisibility(manager.widgets[0].id);

    manager.fitLayoutToViewport(FIXED_VIEWPORT);

    expect(manager.widgets.every((w) => w.hidden === false)).toBe(true);
  });

  it("tells the grid to re-apply, and remembers the result", async () => {
    const { gateway } = makeTwoViewGateway();
    const layouts = makeLayoutRepository();
    const manager = new WorkspaceManager(makeRegistry(), gateway, layouts);

    await manager.selectRecordInDataset("ds-1", "rec-1", FIXED_VIEWPORT);
    const before = manager.layoutRevision;

    manager.fitLayoutToViewport(FIXED_VIEWPORT);

    expect(manager.layoutRevision).toBe(before + 1);
    expect(layouts.load("ds-1")?.views.cam_front.layout).toEqual(
      planViewportLayouts(2, FIXED_VIEWPORT)[0],
    );
  });

  it("does nothing on an empty workspace", () => {
    const { gateway } = makeTwoViewGateway();
    const manager = new WorkspaceManager(makeRegistry(), gateway, makeLayoutRepository());

    expect(() => manager.fitLayoutToViewport(FIXED_VIEWPORT)).not.toThrow();
    expect(manager.layoutRevision).toBe(0);
  });
});
