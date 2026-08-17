/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { describe, expect, it, vi } from "vitest";

import { classifyTool } from "../classifyTool.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { LocalClassification } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import type {
  PendingAnnotation,
  PendingEntityChoice,
  ResourceMutation,
} from "$lib/annotations/types.js";

// The tool builds no Konva nodes at all — there is nothing spatial to draw —
// so an empty stub keeps the module graph loadable in node.
vi.mock("konva", () => ({ default: {} }));

// ─── Harness ─────────────────────────────────────────────────────────────────

function makeHarness(entities: Record<string, Record<string, unknown>> = {}) {
  const collection = new AnnotationCollection();
  const queued: ResourceMutation[] = [];
  let pending: PendingAnnotation | null = null;
  // Held apart from `ctx` so assertions reference plain functions rather than
  // methods read off an interface (which `@typescript-eslint/unbound-method`
  // rightly flags).
  const spies = { setActiveTool: vi.fn(), requestRedraw: vi.fn() };

  const ctx: Scene2DContext = {
    widgetId: "w1",
    buildContext: { datasetId: "ds", recordId: "rec", viewId: "view-1" },
    collection,
    mutations: {
      pending: [],
      queue: (m: ResourceMutation) => queued.push(m),
      upsertUpdate: vi.fn(),
      patchPendingCreate: vi.fn(),
      dropForLocalAnnotation: vi.fn(),
    },
    liveDraft: { get: () => null },
    stage: { getPointerPosition: () => ({ x: 10, y: 10 }) } as unknown as Konva.Stage,
    annotationLayer: { add: vi.fn(), batchDraw: vi.fn() } as unknown as Konva.Layer,
    camera: { imageWidth: 100, imageHeight: 100, calibration: null },
    getKonvaImage: () => null,
    ...spies,
    beginPendingAnnotation: (p: PendingAnnotation) => (pending = p),
    findEntity: (id: string) => entities[id],
    isEntityVisible: () => true,
  };

  return {
    ctx,
    collection,
    queued,
    spies,
    confirm: (choice: PendingEntityChoice) => pending?.onConfirm(choice),
    cancel: () => pending?.onCancel(),
    pendingLabel: () => pending?.label,
  };
}

type PointerEvt = Parameters<
  NonNullable<ReturnType<typeof classifyTool.createHandler>["onPointerDown"]>
>[0];

const evt = () => ({ cancelBubble: false }) as PointerEvt;

const first = (collection: AnnotationCollection): LocalClassification =>
  collection.byKind("classification")[0] as LocalClassification;

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("classifyTool metadata", () => {
  it("declares the classification kind", () => {
    expect(classifyTool.kind).toBe("classification");
    expect(classifyTool.id).toBe("classify");
  });
});

describe("classifyTool creation", () => {
  it("creates a draft on click and asks for its entity", () => {
    const { ctx, collection, pendingLabel } = makeHarness();
    const handler = classifyTool.createHandler(ctx);

    handler.onPointerDown?.(evt());

    expect(collection.byKind("classification")).toHaveLength(1);
    expect(first(collection).persisted).toBe(false);
    expect(pendingLabel()).toBe("classification");
  });

  it("needs no image frame, unlike every spatial kind", () => {
    // `getKonvaImage` returns null in this harness on purpose: a classification
    // annotates the view as a whole, so it must not depend on the frame.
    const { ctx, collection } = makeHarness();
    const handler = classifyTool.createHandler(ctx);

    handler.onPointerDown?.(evt());

    expect(collection.byKind("classification")).toHaveLength(1);
  });

  it("takes its label from a new entity's category", () => {
    const { ctx, collection, confirm } = makeHarness();
    const handler = classifyTool.createHandler(ctx);

    handler.onPointerDown?.(evt());
    confirm({ mode: "new", entityFields: { category: "beach" } });

    expect(first(collection).geometry).toEqual({ labels: ["beach"], confidences: [1] });
  });

  it("takes its label from an existing entity", () => {
    const { ctx, collection, confirm } = makeHarness({
      "ent-1": { id: "ent-1", category: "sunset" },
    });
    const handler = classifyTool.createHandler(ctx);

    handler.onPointerDown?.(evt());
    confirm({ mode: "existing", entityId: "ent-1" });

    expect(first(collection).geometry.labels).toEqual(["sunset"]);
  });

  it("queues the create mutations once the label is known", () => {
    const { ctx, queued, confirm } = makeHarness();
    const handler = classifyTool.createHandler(ctx);

    handler.onPointerDown?.(evt());
    confirm({ mode: "new", entityFields: { category: "beach" } });

    expect(queued.map((m) => m.resource)).toEqual(["entities", "classifications"]);
  });

  it("sends the label the user chose, not the empty draft", () => {
    // The draft is created before the class is known, so the create body must
    // be built from the geometry written at confirm time.
    const { ctx, queued, confirm } = makeHarness();
    const handler = classifyTool.createHandler(ctx);

    handler.onPointerDown?.(evt());
    confirm({ mode: "new", entityFields: { category: "beach" } });

    const body = (queued[1] as Extract<ResourceMutation, { op: "create" }>).body;
    expect(body.labels).toEqual(["beach"]);
    expect(body.confidences).toEqual([1]);
  });

  it("drops the draft when the choice yields no usable label", () => {
    // The backend would accept an empty label list, but a classification that
    // asserts nothing is a row no one can act on.
    const { ctx, collection, queued, confirm } = makeHarness();
    const handler = classifyTool.createHandler(ctx);

    handler.onPointerDown?.(evt());
    confirm({ mode: "new", entityFields: { category: "   " } });

    expect(collection.byKind("classification")).toHaveLength(0);
    expect(queued).toEqual([]);
  });

  it("discards the draft when the form is cancelled", () => {
    const { ctx, collection, cancel } = makeHarness();
    const handler = classifyTool.createHandler(ctx);

    handler.onPointerDown?.(evt());
    cancel();

    expect(collection.byKind("classification")).toHaveLength(0);
  });

  it("hands control back to select after the click", () => {
    const { ctx, spies } = makeHarness();
    const handler = classifyTool.createHandler(ctx);

    handler.onPointerDown?.(evt());

    expect(spies.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("reports which keys it consumed", () => {
    const { ctx } = makeHarness();
    const handler = classifyTool.createHandler(ctx);

    expect(handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Escape" }))).toBe(true);
    expect(handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "a" }))).toBe(false);
  });
});
