/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import type { BBox3DRow, BBoxRow, EntityRow } from "$lib/api/annotations.js";
import type { ImageResponse, PointCloudResponse } from "$lib/api/restTypes.js";
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
  images?: Map<string, ImageResponse>;
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
  it("sets datasetId and recordId on the session", async () => {
    const dataset = makeDataset({ cam: { base: "Image" } });
    const { sink } = makeSink();
    const session = new WorkspaceSession();
    const loader = new RecordLoader({
      workspace: sink,
      registry: makeRegistry(makeImageExtension()),
      gateway: makeGateway({ dataset, images: new Map([["cam", { id: "img-1", src: "/cam.jpg", width: 100, height: 100 } as ImageResponse]]) }),
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
