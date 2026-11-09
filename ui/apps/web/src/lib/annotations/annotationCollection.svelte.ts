/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ClassificationGeometry } from "./kinds/2d/classification/classificationTypes.js";
import type { KeypointsGeometry } from "./kinds/2d/keypoints/keypointsTypes.js";
import type { MaskGeometry } from "./kinds/2d/mask/maskTypes.js";
import type { MultiPathGeometry } from "./kinds/2d/multi-path/multiPathTypes.js";
import {
  storedStatusAfterWrite,
  storedStatusOf,
  type AnnotationReview,
  type ReviewStatus,
} from "./reviewStatus.js";
import type { CoordsNorm, Rotation3x3 } from "./types.js";

/**
 * Every annotation kind the workspace can hold. Adding a kind means adding a
 * literal here plus a module under `lib/annotations/kinds/` — see
 * docs/ARCHITECTURE_TOOLING.md "Adding a new annotation kind".
 */
export type AnnotationKind =
  "bbox" | "bbox3d" | "mask" | "keypoints" | "multi_path" | "classification";

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
  /**
   * Provenance and review status, read from the row by the shared seed
   * envelope (`persistedAnnotation`). Absent on a draft — a person's work, with
   * nothing to review — so draft tools never have to fill it.
   */
  review?: AnnotationReview;
  /**
   * What the dataset holds for this annotation's content, as last read or
   * written — the content an unsaved edit started from. Kept apart from
   * `geometry`/`entityId`/`entity`, which an edit overwrites in place, so that
   * an edit that puts the content back as stored is seen to change nothing, and
   * Discard can put the content back. Absent on a draft no write has carried
   * yet.
   */
  persistedContent?: PersistedContent<G>;
}

/** The part of an annotation a person's edit changes, as the dataset holds it. */
export interface PersistedContent<G = unknown> {
  geometry: G;
  entityId: string;
  entity?: Record<string, unknown>;
}

/**
 * A plain, detached copy of what the dataset holds for an annotation, or
 * undefined when nothing is known. A copy, because the collection's objects are
 * reactive proxies that an edit may change in place: what is restored from it
 * must not move with the edit.
 */
export function copyPersistedContent<G>(
  annotation: LocalAnnotation<G>,
): PersistedContent<G> | undefined {
  const stored = annotation.persistedContent;
  return stored ? ($state.snapshot(stored) as PersistedContent<G>) : undefined;
}

/** Normalized xywh in [0, 1] — same convention as the backend BBox rows. */
export type BBoxGeometry = CoordsNorm;

/** Lance/backend space (Z-up); rotation is a row-major 3×3 matrix. */
export interface BBox3DGeometry {
  coords: [number, number, number, number, number, number];
  /** Server rows may arrive as either; editor output is always "xyzwhd". */
  format: "xyzwhd" | "xyzxyz";
  rotation?: Rotation3x3;
}

export type LocalBBox = LocalAnnotation<BBoxGeometry>;
export type LocalBBox3DAnnotation = LocalAnnotation<BBox3DGeometry>;
export type LocalMask = LocalAnnotation<MaskGeometry>;
export type LocalKeypoints = LocalAnnotation<KeypointsGeometry>;
export type LocalMultiPath = LocalAnnotation<MultiPathGeometry>;
export type LocalClassification = LocalAnnotation<ClassificationGeometry>;

/**
 * Maps each annotation kind to its geometry payload type, so `byKind(kind)`
 * returns annotations typed with the matching geometry (no caller-supplied
 * type argument that could mismatch the kind). Must cover every
 * `AnnotationKind`.
 */
export interface GeometryByKind {
  bbox: BBoxGeometry;
  bbox3d: BBox3DGeometry;
  mask: MaskGeometry;
  keypoints: KeypointsGeometry;
  multi_path: MultiPathGeometry;
  classification: ClassificationGeometry;
}

/**
 * The surface tools, renderers and widgets program against. Implemented by
 * the record-scoped `AnnotationCollection` and by the per-widget
 * `ViewScopedAnnotations` facade, so plugins never know which one they hold.
 *
 * Contract / substitutability note: an `AnnotationStore` represents the set of
 * annotations *relevant to its holder*. For the record-scoped collection that
 * is every annotation; for `ViewScopedAnnotations` it is one view's
 * annotations plus record-scoped kinds. Every read — `items`/`find`/`byKind`/
 * `count` AND `selected`/`selectedId` — is scoped to that relevant set: a
 * selection pointing at an annotation this view can't show reads as no
 * selection, so each widget only reports `hasSelection` (and lets its delete
 * act) on something it actually displays. Writes pass through to the shared
 * record, so a holder should only `add`/`setGeometry`/`select` annotations its
 * own view can see.
 *
 * A holder may also filter what it *displays* (`ViewScopedAnnotations`'
 * display predicate): the display reads — `items`/`byKind`/`count`/`selected`/
 * `selectedId` — honour it, `find` never does. `find` is the lifecycle's
 * lookup (commit an edit, flip `persisted`, a HUD saving the box it holds), and
 * a row hidden from view is still a row: an edit already under way on it must
 * still reach the queue.
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
  /** Assign the annotation's parent entity (id + optional label snapshot). */
  setEntity(id: string, entityId: string, entity?: Record<string, unknown>): void;
  /** Replace the annotation's review state (an Accept taken, not yet saved). */
  setReview(id: string, review: AnnotationReview): void;
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

  setEntity(id: string, entityId: string, entity?: Record<string, unknown>): void {
    const annotation = this.find(id);
    if (annotation) {
      annotation.entityId = entityId;
      annotation.entity = entity;
    }
  }

  /**
   * Show a new review state. The stored status stays what it was: only a write
   * of the row moves it (`recordWrite`), so an Accept still unsaved is never
   * mistaken for one the server holds.
   */
  setReview(id: string, review: AnnotationReview): void {
    const annotation = this.find(id);
    if (!annotation) return;
    const stored = annotation.review?.storedStatus;
    annotation.review = stored === undefined ? review : { ...review, storedStatus: stored };
  }

  /**
   * The annotation's content as it is now, as a detached copy: what a body
   * queued for it now carries. A copy, because the collection's objects are
   * reactive proxies that a later edit may change in place. Undefined when the
   * annotation is not here.
   */
  contentOf(id: string): PersistedContent | undefined {
    const annotation = this.find(id);
    if (!annotation) return undefined;
    const content: PersistedContent = {
      geometry: annotation.geometry,
      entityId: annotation.entityId,
      entity: annotation.entity,
    };
    return $state.snapshot(content);
  }

  /**
   * Record, as a write of this annotation leaves for the backend, what the
   * dataset holds once it lands: the content the write carries, and, for an
   * update, the status the server stores for that body
   * (`storedStatusAfterWrite`). The status shown moves with the stored one when
   * it showed the stored one — no unsaved Accept — so an edit of a model's row
   * reads accepted as its write leaves, without waiting for the save's
   * read-back; an unsaved Accept already shows it.
   *
   * The content is the one taken when the body was queued (`contentOf`), not
   * the annotation's content now: a write retried after a failure leaves with
   * newer edits queued behind it, which it does not carry. A write that carries
   * no content — an Accept alone — leaves the content recorded as it was.
   *
   * Recorded when the write leaves rather than when it lands, so that work
   * begun while it is in flight is measured against what the dataset will hold
   * once it lands: an edit taken back to the content on the wire sends nothing
   * (the content compared is `persistedContent`), and a row whose edit is on
   * the wire already reads accepted, and is not offered Accept again. Returns
   * how to put the previous record back if the write fails — the status shown
   * included, when it moved and nothing has moved it since; nothing when the
   * annotation is not in this collection.
   *
   * @param id The annotation the write is about.
   * @param write `content`: what the write carries, if any; `updateBody`: the
   *   body of an update (a create moves no status).
   */
  recordWrite(
    id: string,
    write: { content?: PersistedContent; updateBody?: Readonly<Record<string, unknown>> },
  ): (() => void) | undefined {
    const annotation = this.find(id);
    if (!annotation) return undefined;
    const previousContent = annotation.persistedContent;
    const previousStored = annotation.review?.storedStatus;
    const previousShown = annotation.review?.status;
    let shownMovedTo: ReviewStatus | "" | undefined;

    if (write.content) annotation.persistedContent = write.content;
    const review = annotation.review;
    if (review && write.updateBody) {
      const showedStored = review.status === storedStatusOf(review);
      const stored = storedStatusAfterWrite(review, write.updateBody);
      review.storedStatus = stored;
      if (showedStored && review.status !== stored) {
        review.status = stored;
        shownMovedTo = stored;
      }
    }

    return () => {
      annotation.persistedContent = previousContent;
      const current = annotation.review;
      if (!current) return;
      current.storedStatus = previousStored;
      // Put back only a status nothing has moved since the write left.
      const untouched = shownMovedTo !== undefined && current.status === shownMovedTo;
      if (untouched && previousShown !== undefined) current.status = previousShown;
    };
  }

  /**
   * Put every annotation back as the dataset holds it — its content and status
   * as last read or written — and drop the drafts and the selection: what
   * Discard shows at once, before the rows are read again. A gesture made while
   * they are read then starts from what is stored, never from discarded work.
   */
  restoreStored(): void {
    this.items = this.items.filter((annotation) => annotation.persisted);
    for (const annotation of this.items) {
      const stored = copyPersistedContent(annotation);
      if (stored) {
        annotation.geometry = stored.geometry;
        annotation.entityId = stored.entityId;
        annotation.entity = stored.entity;
      }
      const review = annotation.review;
      if (review) annotation.review = { ...review, status: storedStatusOf(review) };
    }
    this.selectedId = null;
  }

  /**
   * Take the rows just read, merged with the work done here meanwhile: each
   * annotation holding work not saved yet keeps the version here — replacing
   * it would show the record without work the queue still holds — and every
   * other one becomes its row. Drafts drawn meanwhile stay; an annotation
   * deleted here stays deleted; the selection stays while its annotation
   * exists.
   *
   * Only the kinds actually read are replaced. A kind whose rows could not be
   * read keeps every annotation it shows: a failed request says nothing about
   * what the dataset holds, and taking it for an empty table would take the
   * whole kind off the screen.
   *
   * In place, so this stays the collection every widget holds: a tool or an
   * editor in the middle of a gesture — work staged, not queued yet — keeps
   * working on the record it started on, and commits by id onto the row read.
   *
   * @param rows The annotations the seed loaders built from the rows read.
   * @param holdsWork Whether an annotation has a write still queued or on the wire.
   * @param kindsRead The kinds whose rows were read; `rows` holds only these.
   */
  takeRowsRead(
    rows: readonly LocalAnnotation[],
    holdsWork: (id: string) => boolean,
    kindsRead: ReadonlySet<AnnotationKind>,
  ): void {
    const read = new Set(rows.map((row) => row.id));
    const items: LocalAnnotation[] = [];
    for (const row of rows) {
      if (!holdsWork(row.id)) {
        items.push(row);
        continue;
      }
      const local = this.find(row.id);
      if (local) items.push(local);
    }
    for (const annotation of this.items) {
      const kept =
        !annotation.persisted || holdsWork(annotation.id) || !kindsRead.has(annotation.kind);
      if (kept && !read.has(annotation.id)) items.push(annotation);
    }
    this.items = items;
    if (this.selectedId !== null && !this.find(this.selectedId)) this.selectedId = null;
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
 *
 * `isShown` is the display filter on top of the view rule; it shows everything
 * unless given. It applies to what the widget displays and lets the user act
 * on (`items`, `byKind`, `count`, `selected`, `selectedId`) and never to
 * `find`, so the annotation lifecycle (commit, save, a HUD's edit) still
 * reaches a row the filter hides (see `AnnotationStore`).
 */
export class ViewScopedAnnotations implements AnnotationStore {
  constructor(
    private readonly getParent: () => AnnotationCollection,
    private readonly viewId: string,
    private readonly isShown: (annotation: LocalAnnotation) => boolean = () => true,
  ) {}

  /** The view rule: this view's annotations plus every record-scoped one. */
  private _inView(annotation: LocalAnnotation): boolean {
    return annotation.viewId === this.viewId || RECORD_SCOPED_KINDS.has(annotation.kind);
  }

  /** What the widget displays: the view rule, then the display filter. */
  private _displayed(annotation: LocalAnnotation): boolean {
    return this._inView(annotation) && this.isShown(annotation);
  }

  get items(): LocalAnnotation[] {
    return this.getParent().items.filter((a) => this._displayed(a));
  }

  // Selection is shared across widgets, but each view only "owns" a selection
  // it can actually show — otherwise a widget reports `hasSelection` (and lets
  // its delete button act) on an annotation belonging to another view.
  get selectedId(): string | null {
    return this.selected?.id ?? null;
  }

  get selected(): LocalAnnotation | undefined {
    const annotation = this.getParent().selected;
    return annotation && this._displayed(annotation) ? annotation : undefined;
  }

  get count(): number {
    return this.items.length;
  }

  find(id: string): LocalAnnotation | undefined {
    const annotation = this.getParent().find(id);
    return annotation && this._inView(annotation) ? annotation : undefined;
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

  setEntity(id: string, entityId: string, entity?: Record<string, unknown>): void {
    this.getParent().setEntity(id, entityId, entity);
  }

  setReview(id: string, review: AnnotationReview): void {
    this.getParent().setReview(id, review);
  }
}
