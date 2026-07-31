/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { bbox3dRenderer2DFactory } from "../bbox3dRenderer2D.js";
import {
  AnnotationCollection,
  type BBox3DGeometry,
} from "$lib/annotations/annotationCollection.svelte.js";
import type {
  LiveAnnotationDraft,
  Scene2DReadContext,
} from "$lib/annotations/scene/sceneContext.js";
import type { CameraCalibration } from "$lib/annotations/types.js";

// The renderer's only Konva node is the wireframe line; the layer it draws into
// is a fake supplied by the harness.
vi.mock("konva", () => {
  class Line {
    destroyed = false;
    readonly listening: boolean;
    readonly dash: number[] | undefined;
    private _points: number[] = [];
    private _visible: boolean;
    constructor(cfg: { visible?: boolean; dash?: number[]; listening?: boolean }) {
      this._visible = cfg.visible ?? true;
      this.dash = cfg.dash;
      this.listening = cfg.listening ?? true;
    }
    points(value?: number[]): number[] {
      if (value !== undefined) this._points = value;
      return this._points;
    }
    visible(value?: boolean): boolean {
      if (value !== undefined) this._visible = value;
      return this._visible;
    }
    moveToTop(): void {}
    destroy(): void {
      this.destroyed = true;
    }
  }
  return { default: { Line } };
});

/** Identity extrinsics + unit focal length: world coords pass straight through. */
const CALIBRATION: CameraCalibration = {
  f: [1, 1],
  c: [0, 0],
  distortion: [],
  extrinsicMatrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
  egoToWorld: [],
};

/** Centred 2 units in front of the camera, so all 8 corners stay at z > 0. */
const GEOMETRY: BBox3DGeometry = { coords: [0, 0, 2, 1, 1, 1], format: "xyzwhd" };

function fakeImage(): Konva.Image {
  return { x: () => 0, y: () => 0, width: () => 100, height: () => 100 } as unknown as Konva.Image;
}

function draftFor(editingId: string | null, z = 2): LiveAnnotationDraft {
  return {
    kind: "bbox3d",
    geometry: { coords: [0, 0, z, 1, 1, 1], format: "xyzwhd" },
    editingId,
    sourceWidgetId: "w1",
  };
}

interface FakeLine {
  destroyed: boolean;
  readonly listening: boolean;
  readonly dash: number[] | undefined;
  points(): number[];
  visible(): boolean;
}

interface HarnessOptions {
  /** null models a widget whose view has no camera calibration. */
  calibration?: CameraCalibration | null;
  /** null models a widget whose image has not loaded yet. */
  image?: Konva.Image | null;
  /** Entity ids to treat as hidden by the show/hide filter. */
  hiddenEntityIds?: string[];
}

function makeHarness(opts: HarnessOptions = {}) {
  const { calibration = CALIBRATION, image = fakeImage(), hiddenEntityIds = [] } = opts;
  const hidden = new Set(hiddenEntityIds);
  const collection = new AnnotationCollection();
  let liveDraft: LiveAnnotationDraft | null = null;
  const added: FakeLine[] = [];
  const ctx = {
    widgetId: "w1",
    buildContext: { datasetId: "ds", recordId: "rec", viewId: "" },
    collection,
    // The renderer never reads the stage; only the layer it draws into.
    stage: {} as Konva.Stage,
    annotationLayer: {
      add: (node: unknown) => added.push(node as FakeLine),
      batchDraw: vi.fn(),
    } as unknown as Konva.Layer,
    camera: { imageWidth: 100, imageHeight: 100, calibration },
    liveDraft: { get: () => liveDraft },
    getKonvaImage: () => image,
    requestRedraw: vi.fn(),
    isEntityVisible: (entityId: string) => !hidden.has(entityId),
  } satisfies Scene2DReadContext;

  return {
    ctx,
    collection,
    renderer: bbox3dRenderer2DFactory.create(ctx),
    setDraft: (draft: LiveAnnotationDraft | null) => (liveDraft = draft),
    /** Every line node the renderer has ever added to the layer. */
    lines: added,
    liveLines: () => added.filter((line) => !line.destroyed),
  };
}

/** Add a persisted bbox3d to the harness collection. */
function addBox(
  env: ReturnType<typeof makeHarness>,
  id: string,
  geometry: BBox3DGeometry,
  opts: { entityId?: string; persisted?: boolean } = {},
) {
  env.collection.add({
    id,
    entityId: opts.entityId ?? "e1",
    kind: "bbox3d",
    viewId: "",
    geometry,
    persisted: opts.persisted ?? true,
  });
}

/** Every distinct endpoint across a wireframe's lines, sorted for comparison. */
function cornerPixels(lines: FakeLine[]): string[] {
  const points = new Set<string>();
  for (const line of lines) {
    const [x1, y1, x2, y2] = line.points();
    points.add(`${x1.toFixed(4)},${y1.toFixed(4)}`);
    points.add(`${x2.toFixed(4)},${y2.toFixed(4)}`);
  }
  return [...points].sort();
}

describe("BBox3DRenderer2D.sync", () => {
  it("projects a box through the calibration into stage pixels", () => {
    const env = makeHarness();
    addBox(env, "b1", GEOMETRY);
    env.renderer.sync();

    // f=1, c=0, identity extrinsics, and a 100px image on a 100px frame reduce
    // the pinhole projection to x/z. BOX_EDGES[0] joins corner 0 (-0.5,-0.5,1.5)
    // to corner 1 (0.5,-0.5,1.5), i.e. -1/3 px to +1/3 px at y = -1/3 px.
    const [x1, y1, x2, y2] = env.liveLines()[0].points();
    expect(x1).toBeCloseTo(-1 / 3);
    expect(y1).toBeCloseTo(-1 / 3);
    expect(x2).toBeCloseTo(1 / 3);
    expect(y2).toBeCloseTo(-1 / 3);
  });

  it("gives every box its own wireframe, projected independently", () => {
    const env = makeHarness();
    addBox(env, "b1", GEOMETRY);
    addBox(env, "b2", { coords: [10, 0, 2, 1, 1, 1], format: "xyzwhd" });
    env.renderer.sync();

    const all = env.liveLines();
    expect(all.length % 2).toBe(0);
    const [first, second] = [all.slice(0, all.length / 2), all.slice(all.length / 2)];
    // Guards the shared projection scratch buffers: one box must never inherit
    // the corner pixels left behind by the box projected before it.
    expect(cornerPixels(first)).not.toEqual(cornerPixels(second));
    expect(first[0].points()[0]).toBeCloseTo(-1 / 3);
    expect(second[0].points()[0]).toBeCloseTo(9.5 / 1.5);
  });

  it("destroys a box's lines when it leaves the collection", () => {
    const env = makeHarness();
    addBox(env, "b1", GEOMETRY);
    env.renderer.sync();
    const lines = env.liveLines().slice();

    env.collection.remove("b1");
    env.renderer.sync();

    expect(lines.every((line) => line.destroyed)).toBe(true);
    expect(env.liveLines()).toHaveLength(0);
  });

  it("hides a persisted box whose entity is filtered out", () => {
    const env = makeHarness({ hiddenEntityIds: ["e-hidden"] });
    addBox(env, "b1", GEOMETRY, { entityId: "e-hidden" });
    env.renderer.sync();

    expect(env.liveLines()).toHaveLength(0);
  });

  it("still shows an unsaved box whose entity is filtered out", () => {
    const env = makeHarness({ hiddenEntityIds: ["e-hidden"] });
    addBox(env, "b1", GEOMETRY, { entityId: "e-hidden", persisted: false });
    env.renderer.sync();

    expect(env.liveLines().length).toBeGreaterThan(0);
  });

  it("hides the wireframe when the view has no calibration", () => {
    const env = makeHarness({ calibration: null });
    addBox(env, "b1", GEOMETRY);
    env.renderer.sync();

    expect(env.liveLines().length).toBeGreaterThan(0);
    expect(env.liveLines().every((line) => !line.visible())).toBe(true);
  });

  it("draws nothing until the image has loaded", () => {
    const env = makeHarness({ image: null });
    addBox(env, "b1", GEOMETRY);
    env.renderer.sync();

    expect(env.liveLines()).toHaveLength(0);
  });

  it("treats an identity rotation matrix as no rotation", () => {
    const plain = makeHarness();
    addBox(plain, "b1", GEOMETRY);
    plain.renderer.sync();

    const identity = makeHarness();
    addBox(identity, "b1", { ...GEOMETRY, rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1] });
    identity.renderer.sync();

    expect(cornerPixels(identity.liveLines())).toEqual(cornerPixels(plain.liveLines()));
  });

  it("applies the rotation matrix: a quarter turn about Z swaps the extents", () => {
    const rotated = makeHarness();
    addBox(rotated, "b1", {
      coords: [0, 0, 2, 2, 1, 1],
      format: "xyzwhd",
      rotation: [0, -1, 0, 1, 0, 0, 0, 0, 1], // +90° about Z, row-major
    });
    rotated.renderer.sync();

    // Turning a box a quarter turn about Z lands its 8 corners exactly where
    // the same box with width and height swapped already has them.
    const swapped = makeHarness();
    addBox(swapped, "b1", { coords: [0, 0, 2, 1, 2, 1], format: "xyzwhd" });
    swapped.renderer.sync();

    expect(cornerPixels(rotated.liveLines())).toEqual(cornerPixels(swapped.liveLines()));
  });

  // NaN defeats the ordinary `z <= 0` bail-out, since every comparison with NaN
  // is false — so without an explicit guard the renderer would write NaN line
  // points instead of hiding the box.
  it("hides the wireframe rather than drawing NaN when the geometry is not finite", () => {
    const env = makeHarness();
    addBox(env, "b1", { coords: [0, 0, NaN, 1, 1, 1], format: "xyzwhd" });
    env.renderer.sync();

    expect(env.liveLines().length).toBeGreaterThan(0);
    expect(env.liveLines().every((line) => !line.visible())).toBe(true);
  });

  it("hides the wireframe when the calibration matrix is not finite", () => {
    const env = makeHarness({
      calibration: { ...CALIBRATION, extrinsicMatrix: Array.from({ length: 16 }, () => NaN) },
    });
    addBox(env, "b1", GEOMETRY);
    env.renderer.sync();

    expect(env.liveLines().every((line) => !line.visible())).toBe(true);
  });

  it("destroys every line it owns", () => {
    const env = makeHarness();
    addBox(env, "b1", GEOMETRY);
    env.renderer.sync();
    env.renderer.syncDraft(draftFor(null, 3));
    expect(env.liveLines().length).toBeGreaterThan(0);

    env.renderer.destroy();

    expect(env.liveLines()).toHaveLength(0);
  });
});

describe("BBox3DRenderer2D.syncDraft", () => {
  let env: ReturnType<typeof makeHarness>;

  beforeEach(() => {
    env = makeHarness();
    env.collection.add({
      id: "b1",
      entityId: "e1",
      kind: "bbox3d",
      viewId: "",
      geometry: GEOMETRY,
      persisted: true,
    });
  });

  it("draws a dashed preview and leaves persisted boxes untouched mid-gesture", () => {
    env.renderer.sync();
    const persisted = env.liveLines().slice();
    const persistedPoints = persisted.map((line) => [...line.points()]);

    env.renderer.syncDraft(draftFor(null, 3));

    // The persisted wireframe was not re-projected...
    expect(persisted.map((line) => line.points())).toEqual(persistedPoints);
    expect(persisted.every((line) => !line.destroyed)).toBe(true);
    // ...and a second, dashed wireframe appeared for the draft.
    const draftLines = env.liveLines().filter((line) => !persisted.includes(line));
    expect(draftLines).toHaveLength(persisted.length);
    expect(draftLines.every((line) => line.visible())).toBe(true);
  });

  // The regression this guards: a gesture on an existing box must hide the
  // persisted copy, or the box shows up twice — solid and dashed at once.
  it("hides the edited box when a gesture starts on it (no ghost copy)", () => {
    env.renderer.sync();
    const persisted = env.liveLines().slice();

    env.renderer.syncDraft(draftFor("b1"));

    expect(persisted.every((line) => line.destroyed)).toBe(true);
    expect(env.liveLines().length).toBe(persisted.length); // only the draft remains
  });

  it("restores the edited box and drops the preview when the gesture ends", () => {
    env.renderer.sync();
    env.renderer.syncDraft(draftFor("b1"));
    const duringGesture = env.liveLines().slice();

    env.setDraft(null);
    env.renderer.syncDraft(null);

    // The dashed preview is gone and a fresh persisted wireframe is back.
    expect(duringGesture.every((line) => line.destroyed)).toBe(true);
    expect(env.liveLines().length).toBe(duringGesture.length);
    expect(env.liveLines().every((line) => line.visible())).toBe(true);
  });

  // Wireframes are display-only. A listening line would sit between the user
  // and the stage, so `selectTool2D`'s click-empty-canvas-to-deselect (which
  // tests `event.target === stage`) would silently stop firing over the box.
  it("never lets a wireframe intercept pointer events", () => {
    env.renderer.sync();
    env.renderer.syncDraft(draftFor(null, 3));

    expect(env.liveLines()).not.toHaveLength(0);
    expect(env.liveLines().every((line) => line.listening === false)).toBe(true);
  });

  it("gives each line its own dash array rather than sharing one", () => {
    env.renderer.sync();
    const persisted = env.liveLines().slice();
    env.renderer.syncDraft(draftFor(null, 3));

    const draftLines = env.liveLines().filter((line) => !persisted.includes(line));
    expect(draftLines.every((line) => line.dash?.join() === "6,4")).toBe(true);
    expect(new Set(draftLines.map((line) => line.dash)).size).toBe(draftLines.length);
  });

  // The persisted copy of a hidden box is already suppressed by the reconcile,
  // so drawing its preview would blink it into view for exactly the length of
  // the gesture — visible while dragged, gone before and after.
  it("keeps the preview hidden when the edited box's entity is filtered out", () => {
    const env = makeHarness({ hiddenEntityIds: ["e-hidden"] });
    addBox(env, "b1", GEOMETRY, { entityId: "e-hidden" });
    env.renderer.sync();
    expect(env.liveLines()).toHaveLength(0);

    env.renderer.syncDraft(draftFor("b1"));

    expect(env.liveLines()).toHaveLength(0);
  });

  it("shows the preview when the edited box's entity is visible", () => {
    const env = makeHarness();
    addBox(env, "b1", GEOMETRY);
    env.renderer.sync();

    env.renderer.syncDraft(draftFor("b1"));

    expect(env.liveLines().length).toBeGreaterThan(0);
  });

  it("shows the preview of a brand-new box, which has no entity to filter on", () => {
    const env = makeHarness({ hiddenEntityIds: ["e1", ""] });
    addBox(env, "b1", GEOMETRY);
    env.renderer.sync();

    env.renderer.syncDraft(draftFor(null, 3));

    expect(env.liveLines().length).toBeGreaterThan(0);
  });

  it("shows the preview of an unsaved box, whose entity id is not set yet", () => {
    const env = makeHarness({ hiddenEntityIds: [""] });
    addBox(env, "b1", GEOMETRY, { entityId: "", persisted: false });
    env.renderer.sync();

    env.renderer.syncDraft(draftFor("b1"));

    expect(env.liveLines().length).toBeGreaterThan(0);
  });

  it("ignores a draft belonging to another kind", () => {
    env.renderer.sync();
    const before = env.liveLines().length;

    env.renderer.syncDraft({
      kind: "bbox",
      geometry: [0, 0, 1, 1],
      editingId: null,
      sourceWidgetId: "w2",
    });

    expect(env.liveLines().length).toBe(before);
  });

  it("hides the preview rather than drawing stale points when it cannot project", () => {
    env.renderer.sync();
    const persisted = env.liveLines().slice();
    // z = -1 puts every corner behind the camera.
    env.renderer.syncDraft(draftFor(null, -1));

    const draftLines = env.liveLines().filter((line) => !persisted.includes(line));
    expect(draftLines).toHaveLength(persisted.length);
    expect(draftLines.every((line) => !line.visible())).toBe(true);
  });
});
