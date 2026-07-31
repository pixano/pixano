/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { Matrix3, Matrix4, Vector3, Vector4 } from "three";

import type { BBox3DGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import type {
  AnnotationRenderer2D,
  AnnotationRenderer2DFactory,
} from "$lib/annotations/scene/renderer.js";
import {
  DRAFT_DASH,
  getPixelFrame,
  normalizedPointToPixel,
  type PixelFrame,
  type PixelPoint,
} from "$lib/annotations/scene/scene2dGeometry.js";
import type {
  LiveAnnotationDraft,
  Scene2DReadContext,
} from "$lib/annotations/scene/sceneContext.js";

/**
 * Corner pairs of the projected wireframe: the cube's 12 edges plus the two
 * front-face diagonals that mark the box's facing direction. Indexes are into
 * `UNIT_CUBE_CORNERS` (bottom face 0-3, top face 4-7); the two tables must stay
 * in the same order.
 */
const BOX_EDGES: readonly (readonly [number, number])[] = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 0],
  [4, 5],
  [5, 6],
  [6, 7],
  [7, 4],
  [0, 4],
  [1, 5],
  [2, 6],
  [3, 7],
  [2, 5],
  [1, 6],
];

/**
 * Corner offsets of a unit cube centred on the origin, in the order
 * `BOX_EDGES` indexes them (bottom face 0-3, top face 4-7). Scaled by the box
 * size, rotated, then translated by its centre to give the 8 world-space
 * corners — mirroring the backend's `unit_cube_corners`
 * (`src/pixano/schemas/annotations/bbox.py`).
 */
const UNIT_CUBE_CORNERS: readonly (readonly [number, number, number])[] = [
  [-0.5, -0.5, -0.5],
  [0.5, -0.5, -0.5],
  [0.5, 0.5, -0.5],
  [-0.5, 0.5, -0.5],
  [-0.5, -0.5, 0.5],
  [0.5, -0.5, 0.5],
  [0.5, 0.5, 0.5],
  [-0.5, 0.5, 0.5],
];

const BOX_CORNER_COUNT = UNIT_CUBE_CORNERS.length;

/** The live-draft union narrowed to this renderer's kind. */
type BBox3DDraft = Extract<LiveAnnotationDraft, { kind: "bbox3d" }>;

const PROJECTED_EDGE_COLOR = "#f59e0b";
const PROJECTED_EDGE_WIDTH = 2;

/**
 * Renders the "bbox3d" kind on the Konva scene: each 3D box is projected
 * through the widget's camera calibration into a wireframe of `BOX_EDGES`
 * lines. Each box always owns its full set of lines; a projection that fails
 * (missing calibration, or a corner behind the camera) hides them rather than
 * leaving stale geometry.
 *
 * Display-only, and non-interactive with it: the wireframes never listen for
 * pointer events. Nothing selects a bbox3d from an image view today, and the
 * kind has no `createEditor`, so a listening wireframe could only swallow the
 * select tool's click-empty-canvas-to-deselect. Making 3D boxes selectable here
 * means adding a click handler *and* flipping `listening` back on for the
 * persisted lines only — never for the draft, which mirrors another widget's
 * in-flight gesture.
 */
class BBox3DRenderer2D implements AnnotationRenderer2D {
  readonly kind = "bbox3d";

  private readonly boxByBBoxId = new Map<string, Konva.Line[]>();
  /** Dashed wireframe of the live editing gesture, present only mid-gesture. */
  private draftLines: Konva.Line[] | null = null;

  // ─── Projection scratch ───────────────────────────────────────────────────
  // `syncDraft` runs on every pointer move while a 3D box is dragged in another
  // widget, so the projection path must not allocate — CODING_STANDARDS: "never
  // allocate in pointer-event or render-loop code paths". Every buffer below is
  // overwritten per box and is only valid until the next `_projectInto` call;
  // `_applyProjection` is their single, immediate consumer.
  private readonly rotationScratch = new Matrix3();
  private readonly extrinsicsScratch = new Matrix4();
  private readonly centerScratch = new Vector3();
  private readonly cameraPointScratch = new Vector4();
  /** The box's 8 corners in world (Lance, Z-up) space. */
  private readonly worldCorners = UNIT_CUBE_CORNERS.map(() => new Vector3());
  /** The same 8 corners in Konva stage space. */
  private readonly pixelCorners: PixelPoint[] = UNIT_CUBE_CORNERS.map(() => ({ x: 0, y: 0 }));

  /**
   * `editingId` seen at the last reconcile. A change means a gesture started or
   * ended on a persisted box, which flips whether that box is drawn at all —
   * the one thing the `syncDraft` fast path may not decide on its own.
   */
  private lastEditingId: string | null = null;

  /**
   * Whether the current draft may be drawn at all, decided at reconcile time.
   * Cached rather than recomputed in `_syncDraft` because answering it needs
   * `collection.find`, a linear scan over a freshly filtered array — far too
   * costly for a path that runs on every pointer move. Safe to cache: both of
   * its inputs (the edited id, the visible-entity filter) already force a full
   * reconcile whenever they change.
   */
  private draftVisible = true;

  constructor(private readonly ctx: Scene2DReadContext) {}

  sync(): void {
    this._reconcileAll(this._asBBox3DDraft(this.ctx.liveDraft.get()));
  }

  /**
   * Full reconcile against a given draft. Both entry points funnel here so the
   * draft is read once per pass: `sync()` pulls it from the context, while
   * `syncDraft` forwards the one it was handed. Re-reading the context here
   * instead would give the two paths separate sources of truth for one value.
   */
  private _reconcileAll(draft: BBox3DDraft | null): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    const activeIds = new Set<string>();
    this.lastEditingId = draft?.editingId ?? null;
    this.draftVisible = this._computeDraftVisible(draft);

    for (const bbox of this.ctx.collection.byKind("bbox3d")) {
      // Entity-driven visibility, mirroring the 2D bbox renderer: a persisted
      // box whose entity is hidden gets no lines. Drafts are always shown.
      if (bbox.persisted && !this.ctx.isEntityVisible(bbox.entityId)) continue;
      // While a box is being edited, the live draft is the only copy on
      // screen — same rule as the 3D renderer's editingId skip.
      if (bbox.id === draft?.editingId) continue;
      activeIds.add(bbox.id);
      let projectedBox = this.boxByBBoxId.get(bbox.id);
      if (!projectedBox && frame) {
        projectedBox = this._makeProjectedBox();
        for (const line of projectedBox) this.ctx.annotationLayer.add(line);
        this.boxByBBoxId.set(bbox.id, projectedBox);
      }
      if (projectedBox && frame) this._applyProjection(projectedBox, bbox.geometry, frame);
    }

    for (const [id, projectedBox] of this.boxByBBoxId) {
      if (!activeIds.has(id)) {
        for (const line of projectedBox) line.destroy();
        this.boxByBBoxId.delete(id);
      }
    }

    this._syncDraft(draft, frame);
    // Persisted wireframes are (re)built above, so lift the preview back on top
    // — Konva paints in insertion order. Done here rather than in `syncDraft`
    // so the pointer-rate path stays free of it.
    if (this.draftLines) for (const line of this.draftLines) line.moveToTop();
    this.ctx.annotationLayer.batchDraw();
  }

  /**
   * Pointer-rate fast path: reproject only the dashed preview and leave every
   * persisted wireframe alone, so the cost is one box rather than the whole
   * collection. Gesture start/end are the exception — they flip whether the
   * edited box is drawn at all — and delegate to the full reconcile.
   */
  syncDraft(rawDraft: LiveAnnotationDraft | null): void {
    const draft = this._asBBox3DDraft(rawDraft);
    if ((draft?.editingId ?? null) !== this.lastEditingId) {
      this._reconcileAll(draft);
      return;
    }
    this._syncDraft(draft, getPixelFrame(this.ctx.getKonvaImage()));
    this.ctx.annotationLayer.batchDraw();
  }

  /**
   * A gesture editing a persisted box inherits that box's entity visibility:
   * hiding an entity must keep its box hidden while it is dragged too, or the
   * box would blink into view for exactly the duration of the gesture. A draft
   * with no `editingId` is a brand-new box, and an unsaved one has no entity id
   * yet (`isEntityVisible("")` is false under an active filter) — neither has
   * anything to filter on, so both always show.
   */
  private _computeDraftVisible(draft: BBox3DDraft | null): boolean {
    if (!draft?.editingId) return true;
    const edited = this.ctx.collection.find(draft.editingId);
    if (!edited?.persisted) return true;
    return this.ctx.isEntityVisible(edited.entityId);
  }

  /** Narrow the kind-agnostic union the widget hands us down to our own kind. */
  private _asBBox3DDraft(draft: LiveAnnotationDraft | null): BBox3DDraft | null {
    return draft?.kind === "bbox3d" ? draft : null;
  }

  destroy(): void {
    for (const projectedBox of this.boxByBBoxId.values()) {
      for (const line of projectedBox) line.destroy();
    }
    this.boxByBBoxId.clear();
    this._destroyDraft();
  }

  /**
   * Project the live editing gesture (a 3D box mid-draw/drag broadcast by the
   * 3D widget) as a dashed wireframe, so it tracks the pointer in every image
   * view before being saved.
   */
  private _syncDraft(draft: BBox3DDraft | null, frame: PixelFrame | null): void {
    if (!draft || !frame || !this.draftVisible) {
      this._destroyDraft();
      return;
    }
    if (!this.draftLines) {
      this.draftLines = this._makeProjectedBox(DRAFT_DASH);
      for (const line of this.draftLines) this.ctx.annotationLayer.add(line);
    }
    this._applyProjection(this.draftLines, draft.geometry, frame);
  }

  private _destroyDraft(): void {
    if (!this.draftLines) return;
    for (const line of this.draftLines) line.destroy();
    this.draftLines = null;
  }

  /** One hidden line per `BOX_EDGES` entry; `_applyProjection` fills them in. */
  private _makeProjectedBox(dash?: readonly number[]): Konva.Line[] {
    return BOX_EDGES.map(
      () =>
        new Konva.Line({
          points: [],
          stroke: PROJECTED_EDGE_COLOR,
          strokeWidth: PROJECTED_EDGE_WIDTH,
          visible: false,
          // Konva keeps the array by reference, so hand each line its own copy
          // rather than letting all 14 share the module constant.
          dash: dash ? [...dash] : undefined,
          // Display-only (see the class doc): must never intercept a click.
          listening: false,
        }),
    );
  }

  /**
   * Project the geometry and update every wireframe line, or hide them all
   * when the projection fails (no calibration / a corner behind the camera) —
   * lines must never keep stale points, since a box can cross the camera
   * plane between two syncs.
   */
  private _applyProjection(lines: Konva.Line[], geometry: BBox3DGeometry, frame: PixelFrame): void {
    if (!this._projectInto(geometry, frame)) {
      for (const line of lines) line.visible(false);
      return;
    }
    for (let i = 0; i < BOX_EDGES.length; i++) {
      const [a, b] = BOX_EDGES[i];
      const from = this.pixelCorners[a];
      const to = this.pixelCorners[b];
      lines[i].points([from.x, from.y, to.x, to.y]);
      lines[i].visible(true);
    }
  }

  /** Fill `worldCorners` with the box's 8 corners in world (Lance, Z-up) space. */
  private _computeWorldCorners(geometry: BBox3DGeometry): void {
    const [x, y, z, w, h, d] = geometry.coords;
    if (geometry.rotation) this.rotationScratch.fromArray(geometry.rotation).transpose();
    else this.rotationScratch.identity();
    this.centerScratch.set(x, y, z);
    for (let i = 0; i < BOX_CORNER_COUNT; i++) {
      const [cx, cy, cz] = UNIT_CUBE_CORNERS[i];
      this.worldCorners[i]
        .set(cx * w, cy * h, cz * d)
        .applyMatrix3(this.rotationScratch)
        .add(this.centerScratch);
    }
  }

  /**
   * Pinhole-project the box's corners into `pixelCorners` (Konva stage space).
   * Returns false — leaving the buffer stale — when the widget has no
   * calibration or any corner sits behind the camera, which is why callers
   * must hide the lines rather than draw whatever is left in the buffer.
   */
  private _projectInto(geometry: BBox3DGeometry, frame: PixelFrame): boolean {
    const calibration = this.ctx.camera.calibration;
    if (!calibration) return false;
    const { f, c } = calibration;
    this.extrinsicsScratch.fromArray(calibration.extrinsicMatrix).transpose();
    this._computeWorldCorners(geometry);
    for (let i = 0; i < BOX_CORNER_COUNT; i++) {
      const corner = this.worldCorners[i];
      // world -> camera
      const cam = this.cameraPointScratch
        .set(corner.x, corner.y, corner.z, 1)
        .applyMatrix4(this.extrinsicsScratch);
      // Written as `!(z > 0)`, not `z <= 0`: every comparison with NaN is false,
      // so the `<=` form would wave NaN through and write NaN line points. NaN
      // can reach here from corrupt coords or a bad calibration matrix, so this
      // is the guard that makes "a failed projection hides its lines" true.
      if (!(cam.z > 0)) return false; // Behind the camera, or not a number
      // camera -> image pixels -> normalized -> stage pixels
      normalizedPointToPixel(
        ((f[0] * cam.x) / cam.z + c[0]) / this.ctx.camera.imageWidth,
        ((f[1] * cam.y) / cam.z + c[1]) / this.ctx.camera.imageHeight,
        frame,
        this.pixelCorners[i],
      );
    }
    return true;
  }
}

export const bbox3dRenderer2DFactory: AnnotationRenderer2DFactory = {
  kind: "bbox3d",
  create: (ctx: Scene2DReadContext) => new BBox3DRenderer2D(ctx),
};
