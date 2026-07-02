/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { CoordsNorm } from "./types.js";

/**
 * Every annotation kind the workspace can hold. Adding a kind means adding a
 * literal here plus a module under `lib/annotations/kinds/` — see
 * docs/ARCHITECTURE_TOOLING.md "Adding a new annotation kind".
 */
export type AnnotationKind = "bbox" | "bbox3d" | "mask";

/**
 * Kinds that apply to the whole record rather than a single view (e.g. a 3D
 * box lives in the scene, not in one camera). They pass every view filter,
 * which is what lets the image widget project them.
 */
export const RECORD_SCOPED_KINDS: ReadonlySet<AnnotationKind> = new Set(["bbox3d"]);

/**
 * The one local representation shared by every annotation kind. Pure data:
 * rendering, input handling and payload building live in per-kind modules,
 * never as methods here (see docs/ARCHITECTURE_TOOLING.md, decision D4).
 */
export interface LocalAnnotation<G = unknown> {
  id: string;
  entityId: string;
  kind: AnnotationKind;
  /**
   * Id of the view row this annotation belongs to (the image row id for 2D
   * kinds). Record-scoped kinds keep whatever the backend row carried —
   * often "" — and are visible in every view regardless.
   */
  viewId: string;
  /** Per-kind geometry payload, typed in the kind's module. */
  geometry: G;
  /** True once the annotation (and its entity) have been POSTed to the backend. */
  persisted: boolean;
  /**
   * Snapshot of the parent entity's fields, populated for persisted
   * annotations so UIs can display labels without an extra fetch.
   */
  entity?: Record<string, unknown>;
}

/** Normalized xywh in [0, 1] — same convention as the backend BBox rows. */
export type BBoxGeometry = CoordsNorm;

/** Lance/backend space (Z-up); rotation is a row-major 3×3 matrix. */
export interface BBox3DGeometry {
  coords: [number, number, number, number, number, number];
  /** Server rows may arrive as either; editor output is always "xyzwhd". */
  format: "xyzwhd" | "xyzxyz";
  rotation?: number[];
}

export type LocalBBox = LocalAnnotation<BBoxGeometry>;
export type LocalBBox3DAnnotation = LocalAnnotation<BBox3DGeometry>;

/**
 * Maps each annotation kind to its geometry payload type, so `byKind(kind)`
 * returns annotations typed with the matching geometry (no caller-supplied
 * type argument that could mismatch the kind). Must cover every
 * `AnnotationKind`; `mask` has no geometry module yet.
 */
export interface GeometryByKind {
  bbox: BBoxGeometry;
  bbox3d: BBox3DGeometry;
  mask: unknown;
}

/**
 * The surface tools, renderers and widgets program against. Implemented by
 * the record-scoped `AnnotationCollection` and by the per-widget
 * `ViewScopedAnnotations` facade, so plugins never know which one they hold.
 *
 * Contract / substitutability note: an `AnnotationStore` represents the set of
 * annotations *relevant to its holder*. For the record-scoped collection that
 * is every annotation; for `ViewScopedAnnotations` it is one view's
 * annotations plus record-scoped kinds. Reads — `items`/`find`/`byKind`/`count`
 * AND `selected`/`selectedId` — are scoped to that relevant set: a selection
 * pointing at an annotation this view can't show reads as no selection, so each
 * widget only reports `hasSelection` (and lets its delete act) on something it
 * actually displays. Writes pass through to the shared record, so a holder
 * should only `add`/`setGeometry`/`select` annotations its own view can see.
 */
export interface AnnotationStore {
  readonly items: LocalAnnotation[];
  readonly selectedId: string | null;
  readonly selected: LocalAnnotation | undefined;
  readonly count: number;
  find(id: string): LocalAnnotation | undefined;
  byKind<K extends AnnotationKind>(kind: K): LocalAnnotation<GeometryByKind[K]>[];
  add(annotation: LocalAnnotation): void;
  remove(id: string): void;
  select(id: string | null): void;
  setGeometry<G>(id: string, geometry: G): void;
}

/**
 * The single source of truth for one loaded record's annotations: membership,
 * selection, geometry edits and the persisted flip. Owned by
 * `WorkspaceSession` (one instance per record load) and shared by every
 * widget viewing that record — moving a 3D box updates its 2D projection
 * because both read the same annotation.
 *
 * Optimistic edits mutate `geometry` in place; the pending mutation queue is
 * the ledger of what still has to reach the backend.
 */
export class AnnotationCollection implements AnnotationStore {
  items = $state<LocalAnnotation[]>([]);
  selectedId = $state<string | null>(null);

  readonly count = $derived(this.items.length);
  readonly selected = $derived(this.items.find((a) => a.id === this.selectedId));

  constructor(initial: LocalAnnotation[] = []) {
    this.items = initial;
  }

  find(id: string): LocalAnnotation | undefined {
    return this.items.find((a) => a.id === id);
  }

  byKind<K extends AnnotationKind>(kind: K): LocalAnnotation<GeometryByKind[K]>[] {
    return this.items.filter((a) => a.kind === kind) as LocalAnnotation<GeometryByKind[K]>[];
  }

  add(annotation: LocalAnnotation): void {
    this.items.push(annotation);
  }

  /** Remove from the list; clears the selection when it pointed at the removed id. */
  remove(id: string): void {
    this.items = this.items.filter((a) => a.id !== id);
    if (this.selectedId === id) this.selectedId = null;
  }

  select(id: string | null): void {
    this.selectedId = id;
  }

  setGeometry<G>(id: string, geometry: G): void {
    const annotation = this.find(id);
    if (annotation) annotation.geometry = geometry;
  }
}

/**
 * A widget's window onto the shared record collection: shows the annotations
 * of one view plus every record-scoped annotation, while writes (selection,
 * geometry, add/remove) go straight to the shared collection so every other
 * widget sees them immediately.
 *
 * Takes a getter rather than an instance because the session replaces the
 * collection on each record load.
 */
export class ViewScopedAnnotations implements AnnotationStore {
  constructor(
    private readonly getParent: () => AnnotationCollection,
    private readonly viewId: string,
  ) {}

  private _visible(annotation: LocalAnnotation): boolean {
    return annotation.viewId === this.viewId || RECORD_SCOPED_KINDS.has(annotation.kind);
  }

  get items(): LocalAnnotation[] {
    return this.getParent().items.filter((a) => this._visible(a));
  }

  // Selection is shared across widgets, but each view only "owns" a selection
  // it can actually show — otherwise a widget reports `hasSelection` (and lets
  // its delete button act) on an annotation belonging to another view.
  get selectedId(): string | null {
    return this.selected?.id ?? null;
  }

  get selected(): LocalAnnotation | undefined {
    const annotation = this.getParent().selected;
    return annotation && this._visible(annotation) ? annotation : undefined;
  }

  get count(): number {
    return this.items.length;
  }

  find(id: string): LocalAnnotation | undefined {
    const annotation = this.getParent().find(id);
    return annotation && this._visible(annotation) ? annotation : undefined;
  }

  byKind<K extends AnnotationKind>(kind: K): LocalAnnotation<GeometryByKind[K]>[] {
    return this.items.filter((a) => a.kind === kind) as LocalAnnotation<GeometryByKind[K]>[];
  }

  add(annotation: LocalAnnotation): void {
    this.getParent().add(annotation);
  }

  remove(id: string): void {
    this.getParent().remove(id);
  }

  select(id: string | null): void {
    this.getParent().select(id);
  }

  setGeometry<G>(id: string, geometry: G): void {
    this.getParent().setGeometry(id, geometry);
  }
}
