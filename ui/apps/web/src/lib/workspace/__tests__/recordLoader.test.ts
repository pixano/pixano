/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import type { BBox3DRow, BBoxRow, EntityRow } from "$lib/api/annotations.js";
import type { CalibratedImageResponse, PointCloudResponse } from "$lib/api/restTypes.js";
import { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import type { WidgetComponentProps, WidgetExtensionConfig } from "$lib/extensions/types.js";
import { DatasetInfo } from "$lib/types/dataset";
import type { Dataset } from "$lib/types/dataset";
import type { Component } from "svelte";

import type { DatasetGateway } from "../datasetGateway.js";
import { RecordLoader } from "../recordLoader.js";
import type { WidgetSink } from "../recordLoader.js";
import { WorkspaceSession } from "../workspaceSession.svelte.js";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const stubComponent = (() => null) as unknown as Component<WidgetComponentProps>;

function makeDataset(views: Record<string, { base: string }>): Dataset {
  const info = new DatasetInfo({
    id: "ds-1",
    name: "Test Dataset",
    description: "",
    num_items: 2,
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

function makeGateway(opts: {
  dataset?: Dataset;
  entities?: EntityRow[];
  images?: Map<string, CalibratedImageResponse>;
  pointClouds?: Map<string, PointCloudResponse>;
  bboxes?: BBoxRow[];
  bboxes3d?: BBox3DRow[];
} = {}): DatasetGateway {
  return {
    getDataset: () => Promise.resolve(opts.dataset ?? makeDataset({})),
    listEntities: () => Promise.resolve(opts.entities ?? []),
    loadImageByLogicalName: (_, __, name) =>
      Promise.resolve(opts.images?.get(name) ?? null),
    listBBoxes: () => Promise.resolve(opts.bboxes ?? []),
    loadPointCloudByLogicalName: (_, __, name) =>
      Promise.resolve(opts.pointClouds?.get(name) ?? null),
    listBBox3Ds: () => Promise.resolve(opts.bboxes3d ?? []),
    createEntity: () => Promise.resolve({}),
    deleteEntity: () => Promise.resolve(),
    createAnnotation: () => Promise.resolve({}),
    updateAnnotation: () => Promise.resolve({}),
    deleteAnnotation: () => Promise.resolve(),
  };
}

function makeImageExtension(claimedBase = "Image"): WidgetExtensionConfig {
  return {
    name: "image",
    label: "Image",
    icon: "image",
    priority: 100,
    defaultLayout: { x: 0, y: 0, w: 3, h: 3 },
    component: stubComponent,
    addStorage: () => ({ bboxes: [] }),
    addRecordSeed: async ({ viewDef, viewName }) => {
      if (viewDef.base !== claimedBase) return null;
      return { title: viewName, options: {}, storage: {} };
    },
  };
}

function makeRegistry(...extensions: WidgetExtensionConfig[]): WidgetRegistry {
  const registry = new WidgetRegistry();
  for (const ext of extensions) {
    registry.register({ config: ext } as never);
  }
  return registry;
}

function makeSink() {
  const widgets: { extensionName: string; overrides?: unknown }[] = [];
  const sink: WidgetSink = {
    addWidget: (extensionName, overrides) => {
      widgets.push({ extensionName, overrides });
      return null;
    },
  };
  return { sink, widgets };
}

const VIEWPORT = { width: 1600, height: 900 };

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("RecordLoader.load", () => {
  it("runs the per-kind seed loaders once per record against the claimed views", async () => {
    const dataset = makeDataset({ cam_a: { base: "Image" }, cam_b: { base: "Image" } });
    const listBBoxes = vi.fn().mockResolvedValue([
      {
        id: "bb-a",
        record_id: "rec-1",
        entity_id: "e-a",
        view_id: "img-a",
        coords: [0.1, 0.1, 0.2, 0.2],
        format: "xywh",
        is_normalized: true,
      },
      {
        id: "bb-hidden",
        record_id: "rec-1",
        entity_id: "e-x",
        view_id: "not-displayed",
        coords: [0.1, 0.1, 0.2, 0.2],
        format: "xywh",
        is_normalized: true,
      },
    ] as BBoxRow[]);
    const ext: WidgetExtensionConfig = {
      ...makeImageExtension(),
      addRecordSeed: async ({ viewName, viewDef }) => {
        if (viewDef.base !== "Image") return null;
        return {
          title: viewName,
          view: { id: `img-${viewName.slice(-1)}`, logicalName: viewName, width: 100, height: 100 },
        };
      },
    };
    const session = new WorkspaceSession();
    const loader = new RecordLoader({
      workspace: makeSink().sink,
      registry: makeRegistry(ext),
      gateway: { ...makeGateway({ dataset }), listBBoxes },
      session,
    });

    await loader.load("ds-1", "rec-1", VIEWPORT);

    // One record-scoped fetch, not one per view.
    expect(listBBoxes).toHaveBeenCalledTimes(1);
    // The displayed view's row is seeded; the undisplayed one is skipped.
    expect(session.annotations.items.map((a) => a.id)).toEqual(["bb-a"]);
    expect(session.annotations.find("bb-a")).toMatchObject({ viewId: "img-a", persisted: true });
  });

  it("resets the shared collection at the start of a new load", async () => {
    const dataset = makeDataset({ cam: { base: "Image" } });
    const session = new WorkspaceSession();
    session.annotations.add({
      id: "stale",
      entityId: "e",
      kind: "bbox",
      viewId: "old",
      geometry: [0, 0, 1, 1],
      persisted: true,
    });
    const loader = new RecordLoader({
      workspace: makeSink().sink,
      registry: makeRegistry(makeImageExtension()),
      gateway: makeGateway({ dataset }),
      session,
    });

    await loader.load("ds-1", "rec-1", VIEWPORT);

    expect(session.annotations.find("stale")).toBeUndefined();
  });

  it("sets datasetId and recordId on the session", async () => {
    const dataset = makeDataset({ cam: { base: "Image" } });
    const { sink } = makeSink();
    const session = new WorkspaceSession();
    const loader = new RecordLoader({
      workspace: sink,
      registry: makeRegistry(makeImageExtension()),
      gateway: makeGateway({ dataset, images: new Map([["cam", { id: "img-1", record_id: "rec-1", src: "/cam.jpg", width: 100, height: 100, f: null, c: null, distortion: null, extrinsic_matrix: null, ego_to_world: null } as CalibratedImageResponse]]) }),
      session,
    });

    await loader.load("ds-1", "rec-1", VIEWPORT);

    expect(session.datasetId).toBe("ds-1");
    expect(session.recordId).toBe("rec-1");
  });

  it("creates one widget per claimed view in dataset order", async () => {
    const dataset = makeDataset({
      cam_front: { base: "Image" },
      cam_back: { base: "Image" },
    });
    const { sink, widgets } = makeSink();
    const session = new WorkspaceSession();
    const loader = new RecordLoader({
      workspace: sink,
      registry: makeRegistry(makeImageExtension()),
      gateway: makeGateway({ dataset }),
      session,
    });

    await loader.load("ds-1", "rec-1", VIEWPORT);

    expect(widgets).toHaveLength(2);
    expect(widgets[0].extensionName).toBe("image");
    expect(widgets[1].extensionName).toBe("image");
  });

  it("skips views that no extension claims", async () => {
    const dataset = makeDataset({
      cam: { base: "Image" },
      unsupported: { base: "Unknown" },
    });
    const { sink, widgets } = makeSink();
    const session = new WorkspaceSession();
    const loader = new RecordLoader({
      workspace: sink,
      registry: makeRegistry(makeImageExtension()),
      gateway: makeGateway({ dataset }),
      session,
    });

    await loader.load("ds-1", "rec-1", VIEWPORT);

    expect(widgets).toHaveLength(1);
  });

  it("throws when no views are renderable", async () => {
    const dataset = makeDataset({ depth: { base: "Unknown" } });
    const { sink } = makeSink();
    const session = new WorkspaceSession();
    const loader = new RecordLoader({
      workspace: sink,
      registry: makeRegistry(makeImageExtension()),
      gateway: makeGateway({ dataset }),
      session,
    });

    await expect(loader.load("ds-1", "rec-1", VIEWPORT)).rejects.toThrow("No renderable views");
  });

  it("gracefully handles listEntities failure", async () => {
    const dataset = makeDataset({ cam: { base: "Image" } });
    const { sink, widgets } = makeSink();
    const session = new WorkspaceSession();
    const gateway = makeGateway({ dataset });
    gateway.listEntities = () => Promise.reject(new Error("network error"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const loader = new RecordLoader({
      workspace: sink,
      registry: makeRegistry(makeImageExtension()),
      gateway,
      session,
    });

    await loader.load("ds-1", "rec-1", VIEWPORT);

    // Widgets still created despite entity fetch failure
    expect(widgets).toHaveLength(1);
    consoleSpy.mockRestore();
  });

  it("first extension in priority order wins for a shared base", async () => {
    const dataset = makeDataset({ cam: { base: "Image" } });
    const { sink, widgets } = makeSink();
    const session = new WorkspaceSession();
    const highPriority: WidgetExtensionConfig = {
      ...makeImageExtension("Image"),
      name: "high-image",
      priority: 200,
    };
    const lowPriority: WidgetExtensionConfig = {
      ...makeImageExtension("Image"),
      name: "low-image",
      priority: 50,
    };
    const loader = new RecordLoader({
      workspace: sink,
      registry: makeRegistry(highPriority, lowPriority),
      gateway: makeGateway({ dataset }),
      session,
    });

    await loader.load("ds-1", "rec-1", VIEWPORT);

    expect(widgets).toHaveLength(1);
    expect(widgets[0].extensionName).toBe("high-image");
  });

  it("stores loaded entities in the session", async () => {
    const entities: EntityRow[] = [
      { id: "e1", record_id: "rec-1", category: "car" },
      { id: "e2", record_id: "rec-1", category: "person" },
    ];
    const dataset = makeDataset({ cam: { base: "Image" } });
    const { sink } = makeSink();
    const session = new WorkspaceSession();
    const loader = new RecordLoader({
      workspace: sink,
      registry: makeRegistry(makeImageExtension()),
      gateway: makeGateway({ dataset, entities }),
      session,
    });

    await loader.load("ds-1", "rec-1", VIEWPORT);

    expect(session.entities).toHaveLength(2);
    expect(session.entities[0].id).toBe("e1");
    expect(session.entities[1].id).toBe("e2");
  });

  it("clears session entities at the start of a new load", async () => {
    const dataset = makeDataset({ cam: { base: "Image" } });
    const { sink } = makeSink();
    const session = new WorkspaceSession();
    session.entities = [{ id: "stale", record_id: "old-rec" }];

    let resolveEntities!: (rows: EntityRow[]) => void;
    const entitiesPromise = new Promise<EntityRow[]>((res) => { resolveEntities = res; });

    const gateway = makeGateway({ dataset });
    gateway.listEntities = () => entitiesPromise;
    const loader = new RecordLoader({
      workspace: sink,
      registry: makeRegistry(makeImageExtension()),
      gateway,
      session,
    });

    const loadPromise = loader.load("ds-1", "rec-1", VIEWPORT);
    // Entities cleared immediately when load starts, before the fetch resolves
    expect(session.entities).toEqual([]);
    resolveEntities([]);
    await loadPromise;
  });

  it("stores empty entities array when listEntities fails", async () => {
    const dataset = makeDataset({ cam: { base: "Image" } });
    const { sink } = makeSink();
    const session = new WorkspaceSession();
    const gateway = makeGateway({ dataset });
    gateway.listEntities = () => Promise.reject(new Error("network error"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const loader = new RecordLoader({
      workspace: sink,
      registry: makeRegistry(makeImageExtension()),
      gateway,
      session,
    });

    await loader.load("ds-1", "rec-1", VIEWPORT);

    expect(session.entities).toEqual([]);
    consoleSpy.mockRestore();
  });

  it("passes entitiesById to each extension seed", async () => {
    const entity: EntityRow = { id: "e1", record_id: "rec-1", category: "car" };
    const dataset = makeDataset({ cam: { base: "Image" } });
    let capturedEntitiesById: Map<string, EntityRow> | undefined;

    const ext: WidgetExtensionConfig = {
      ...makeImageExtension("Image"),
      name: "spy-ext",
      addRecordSeed: async ({ viewDef, entitiesById }) => {
        if (viewDef.base !== "Image") return null;
        capturedEntitiesById = entitiesById;
        return { title: "cam", options: {}, storage: {} };
      },
    };

    const { sink } = makeSink();
    const session = new WorkspaceSession();
    const loader = new RecordLoader({
      workspace: sink,
      registry: makeRegistry(ext),
      gateway: makeGateway({ dataset, entities: [entity] }),
      session,
    });

    await loader.load("ds-1", "rec-1", VIEWPORT);

    expect(capturedEntitiesById?.get("e1")).toEqual(entity);
  });
});

describe("RecordLoader.reloadEntities", () => {
  it("refreshes session.entities for the current record", async () => {
    const dataset = makeDataset({ cam: { base: "Image" } });
    const session = new WorkspaceSession();
    let call = 0;
    const gateway = makeGateway({ dataset });
    gateway.listEntities = () => {
      call++;
      return Promise.resolve(
        call === 1 ? [{ id: "e-old", record_id: "rec-1" }] : [{ id: "e-new", record_id: "rec-1" }],
      );
    };
    const loader = new RecordLoader({
      workspace: makeSink().sink,
      registry: makeRegistry(makeImageExtension()),
      gateway,
      session,
    });

    await loader.load("ds-1", "rec-1", VIEWPORT);
    expect(session.entities.map((e) => e.id)).toEqual(["e-old"]);

    await loader.reloadEntities();
    expect(session.entities.map((e) => e.id)).toEqual(["e-new"]);
  });

  it("discards a stale reload when a newer record load started during the fetch", async () => {
    const dataset = makeDataset({ cam: { base: "Image" } });
    const session = new WorkspaceSession();

    let call = 0;
    let resolveReload!: (rows: EntityRow[]) => void;
    const gateway = makeGateway({ dataset });
    gateway.listEntities = () => {
      call++;
      // 1: load rec-A, 2: the reload (held in-flight), 3: load rec-B.
      if (call === 2) return new Promise<EntityRow[]>((res) => (resolveReload = res));
      return Promise.resolve(call === 1 ? [{ id: "e-A", record_id: "rec-A" }] : [{ id: "e-B", record_id: "rec-B" }]);
    };
    const loader = new RecordLoader({
      workspace: makeSink().sink,
      registry: makeRegistry(makeImageExtension()),
      gateway,
      session,
    });

    await loader.load("ds-1", "rec-A", VIEWPORT);
    const reloadPromise = loader.reloadEntities(); // captures the current token, then awaits
    await loader.load("ds-1", "rec-B", VIEWPORT); // bumps loadToken, sets entities to rec-B
    resolveReload([{ id: "e-A", record_id: "rec-A" }]); // stale fetch resolves last
    await reloadPromise;

    // The stale reload must NOT clobber record B's entities.
    expect(session.entities.map((e) => e.id)).toEqual(["e-B"]);
  });
});
