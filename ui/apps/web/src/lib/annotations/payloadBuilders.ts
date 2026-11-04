/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  AnnotationKind,
  AnnotationStore,
  LocalAnnotation,
} from "./annotationCollection.svelte.js";
import { buildEntityCreateMutation, generateShortId } from "./buildPayloads.js";
import type { BuildContext, EntityCreateChoice } from "./buildPayloads.js";
import { bboxPayloadBuilder } from "./kinds/2d/bbox/bboxPayloadBuilder.js";
import { classificationPayloadBuilder } from "./kinds/2d/classification/classificationPayloadBuilder.js";
import { keypointsPayloadBuilder } from "./kinds/2d/keypoints/keypointsPayloadBuilder.js";
import { maskPayloadBuilder } from "./kinds/2d/mask/maskPayloadBuilder.js";
import { multiPathPayloadBuilder } from "./kinds/2d/multi-path/multiPathPayloadBuilder.js";
import { bbox3dPayloadBuilder } from "./kinds/3d/bbox3d/bbox3dPayloadBuilder.js";
import { carriesContent, isReviewable, MODEL_SOURCE_TYPE } from "./reviewStatus.js";
import type { MutationSink } from "./scene/sceneContext.js";
import type { PendingAnnotation, PendingEntityChoice, ResourceMutation } from "./types.js";

/**
 * Per-kind knowledge of how a `LocalAnnotation` becomes backend payloads.
 * One entry per kind in `PAYLOAD_BUILDERS`; nothing outside the kind's
 * module knows its resource name or body shape.
 */
export interface PayloadBuilder<G = unknown> {
  kind: AnnotationKind;
  /** Backend collection name, e.g. "bboxes". */
  resource: string;
  /**
   * Mutations creating the annotation and its parent entity. `entity` carries
   * the user's entity choice (new fields, or link-existing to skip the
   * entity-create); omitted means a new anonymous entity.
   */
  buildCreate(
    ctx: BuildContext,
    annotation: LocalAnnotation<G>,
    widgetId: string,
    entity?: EntityCreateChoice,
  ): ResourceMutation[];
  /** Update body for an existing annotation whose geometry changed. */
  buildUpdate(ctx: BuildContext, annotation: LocalAnnotation<G>): Record<string, unknown>;
  /**
   * The geometry this annotation must take when it moves onto `entity`, or
   * `null` to refuse the move. Only for a kind whose payload derives from its
   * entity; every other kind carries geometry independent of it and leaves
   * this out.
   *
   * Exists for one real case: a classification's labels *are* the entity's
   * label, so moving it to another entity without rewriting them would leave a
   * chip asserting a class the annotation no longer belongs to.
   *
   * It lives on the builder, not on the call that opens the entity form: a
   * reassignment is reachable from the widget toolbar, a keyboard shortcut and
   * a kind's own gesture, and a rule only one of those entry points knew about
   * saved the stale class from the two others.
   */
  geometryForEntity?(
    annotation: LocalAnnotation<G>,
    entity: Record<string, unknown> | undefined,
  ): G | null;
}

const PAYLOAD_BUILDERS: ReadonlyMap<AnnotationKind, PayloadBuilder> = new Map<
  AnnotationKind,
  PayloadBuilder
>([
  [bboxPayloadBuilder.kind, bboxPayloadBuilder as PayloadBuilder],
  [bbox3dPayloadBuilder.kind, bbox3dPayloadBuilder as PayloadBuilder],
  [maskPayloadBuilder.kind, maskPayloadBuilder as PayloadBuilder],
  [keypointsPayloadBuilder.kind, keypointsPayloadBuilder as PayloadBuilder],
  [multiPathPayloadBuilder.kind, multiPathPayloadBuilder as PayloadBuilder],
  [classificationPayloadBuilder.kind, classificationPayloadBuilder as PayloadBuilder],
]);

export function payloadBuilderFor(kind: AnnotationKind): PayloadBuilder {
  const builder = PAYLOAD_BUILDERS.get(kind);
  if (!builder) throw new Error(`No payload builder registered for annotation kind "${kind}"`);
  return builder;
}

/**
 * The slice of a scene context the commit helpers need. Both `Scene2DContext`
 * and the widgets' `SceneContextBase` seam satisfy it, so the same commit path
 * serves every tool, renderer and widget.
 */
export interface CommitContext {
  buildContext: BuildContext;
  collection: AnnotationStore;
  mutations: MutationSink;
  widgetId: string;
}

/**
 * Commit a freshly drawn annotation: add it to the shared collection as a draft
 * (`persisted: false`) and queue its create mutations. Kind-agnostic — the
 * mutations come from the kind's payload builder. Returns the new annotation.
 */
export function commitNewAnnotation<G>(
  ctx: CommitContext,
  kind: AnnotationKind,
  geometry: G,
  ids: { id?: string; entityId?: string } = {},
): LocalAnnotation<G> {
  const builder = payloadBuilderFor(kind);
  const annotation: LocalAnnotation<G> = {
    id: ids.id ?? generateShortId(),
    entityId: ids.entityId ?? generateShortId(),
    kind,
    viewId: ctx.buildContext.viewId,
    geometry,
    persisted: false,
  };
  ctx.collection.add(annotation);
  for (const m of builder.buildCreate(ctx.buildContext, annotation, ctx.widgetId)) {
    ctx.mutations.queue(m);
  }
  return annotation;
}

/**
 * Commit a geometry edit to an existing local annotation: write it into the
 * collection, then either queue an update (persisted, `queueContentEdit`) or
 * patch its still-pending create (draft). Kind-agnostic — the body comes from
 * the kind's `buildUpdate`, which is a superset of the create body's geometry
 * fields, so patching a pending create with it only changes the geometry.
 */
export function commitGeometryEdit<G>(ctx: CommitContext, annotationId: string, geometry: G): void {
  const annotation = ctx.collection.find(annotationId);
  if (!annotation) return;
  ctx.collection.setGeometry(annotationId, geometry);

  if (annotation.persisted) {
    queueContentEdit(ctx, annotation);
    return;
  }
  const builder = payloadBuilderFor(annotation.kind);
  // INVARIANT (D9): the create body must be a superset of `buildUpdate`'s
  // fields, with identical values for everything except geometry. Then merging
  // this body into the queued create changes only the geometry. A future kind
  // whose buildUpdate diverges from buildCreate on a shared field would break
  // this — keep them aligned (covered by commit.test.ts).
  ctx.mutations.patchPendingCreate(
    annotation.id,
    builder.resource,
    builder.buildUpdate(ctx.buildContext, annotation),
  );
}

/** What queueing an edit of a stored annotation's content needs. */
interface ContentEditContext {
  readonly mutations: Pick<MutationSink, "pending" | "upsertUpdate" | "dropForLocalAnnotation">;
  readonly buildContext: BuildContext;
  readonly widgetId: string;
}

/**
 * Queue what an edit of a stored annotation's content calls for — its geometry
 * or its entity, already written to the collection. One place for every edit
 * gesture, of every kind.
 *
 * An edit of a model's row leaves the status it shows alone: unsaved, the row
 * stays in review — pending — until the edit is saved, which the server stores
 * accepted (the row then reads so as its write leaves,
 * `AnnotationCollection.recordWrite`).
 *
 * - **Content back as stored** — a drag undone by hand, the entity it already
 *   had picked again — is not an edit: nothing of it is sent, since the server
 *   would store nothing. A content edit queued earlier for the row is dropped
 *   (with an entity a reassignment queued for it).
 * - **Any other edit** replaces the content the row's queued update carried.
 */
function queueContentEdit(ctx: ContentEditContext, annotation: LocalAnnotation): void {
  const builder = payloadBuilderFor(annotation.kind);
  const body = builder.buildUpdate(ctx.buildContext, annotation);
  if (leavesContentAsStored(ctx.buildContext, annotation, body)) {
    if (queuedContentEdit(ctx.mutations.pending, builder.resource, annotation.id) !== undefined) {
      ctx.mutations.dropForLocalAnnotation(annotation.id);
    }
    return;
  }
  ctx.mutations.upsertUpdate({
    op: "update",
    resource: builder.resource,
    id: annotation.id,
    body,
    widgetId: ctx.widgetId,
    localAnnotationId: annotation.id,
  });
}

/**
 * The body of the update queued for this row when it carries an edit of the
 * row's content — geometry, entity — rather than the status alone; undefined
 * otherwise. The latest queued update is the one read, the one `upsertUpdate`
 * replaces: after a failed request, a row may hold that one and a newer one
 * queued while it was on the wire.
 */
function queuedContentEdit(
  pending: readonly ResourceMutation[],
  resource: string,
  annotationId: string,
): Readonly<Record<string, unknown>> | undefined {
  const queued = pending.findLast(
    (m) => m.op === "update" && m.resource === resource && m.id === annotationId,
  );
  return queued?.op === "update" && carriesContent(queued.body) ? queued.body : undefined;
}

/**
 * How far apart two numbers of an update body may be and still be one value,
 * relative to their size (and absolute below 1): eight units in the last place
 * of a float32, the precision the dataset stores coordinates in. A value read
 * back from storage, or converted by the client and back — a 3D box's rotation
 * goes through a quaternion — lands within a unit or two of where it was; no
 * edit made by hand is anywhere near this small.
 */
const FLOAT32_ROUND_TRIP_TOLERANCE = 2 ** -20;

/**
 * Whether an update body for the annotation, as edited, carries what the
 * dataset holds already — then the edit changes nothing the server would see.
 *
 * Compared as the server compares it: the body the kind builds from the
 * annotation, against the body it builds from the stored content, minus a
 * model's score (which no edit of a model's row changes — the columns the
 * kind's loader declared, `AnnotationReview.scoreFields`), with floats as close
 * as storage keeps them. Kind-agnostic: only the kind's own `buildUpdate` and
 * declaration are used. Unknown — nothing stored to compare with — reads as a
 * change.
 */
function leavesContentAsStored(
  buildContext: BuildContext,
  annotation: LocalAnnotation,
  body: Readonly<Record<string, unknown>>,
): boolean {
  const stored = annotation.persistedContent;
  if (!stored) return false;
  const storedBody = payloadBuilderFor(annotation.kind).buildUpdate(buildContext, {
    ...annotation,
    geometry: stored.geometry,
    entityId: stored.entityId,
    entity: stored.entity,
  });
  const review = annotation.review;
  const isModelRow = review?.sourceType === MODEL_SOURCE_TYPE;
  const ignored = new Set(isModelRow ? (review?.scoreFields ?? []) : []);
  const keys = new Set([...Object.keys(body), ...Object.keys(storedBody)]);
  return [...keys].every((key) => ignored.has(key) || sameValue(body[key], storedBody[key]));
}

/**
 * Deep equality over plain data, numbers within `FLOAT32_ROUND_TRIP_TOLERANCE`:
 * what the dataset keeps as one value. Shared, so that whatever compares
 * content with what storage gives back reads "unchanged" as this rule does.
 */
export function sameValue(a: unknown, b: unknown): boolean {
  if (typeof a === "number" && typeof b === "number") {
    if (Number.isNaN(a) || Number.isNaN(b)) return Number.isNaN(a) && Number.isNaN(b);
    const scale = Math.max(1, Math.abs(a), Math.abs(b));
    return Math.abs(a - b) <= FLOAT32_ROUND_TRIP_TOLERANCE * scale;
  }
  const aList = asList(a);
  const bList = asList(b);
  if (aList || bList) {
    return (
      aList !== undefined &&
      bList !== undefined &&
      aList.length === bList.length &&
      aList.every((item, index) => sameValue(item, bList[index]))
    );
  }
  if (isPlainObject(a) && isPlainObject(b)) {
    // A key holding `undefined` is a key JSON does not send.
    const keys = new Set(
      [...Object.keys(a), ...Object.keys(b)].filter(
        (key) => a[key] !== undefined || b[key] !== undefined,
      ),
    );
    return [...keys].every((key) => sameValue(a[key], b[key]));
  }
  return a === b;
}

/** An array or a typed array as a list of its items; undefined for anything else. */
function asList(value: unknown): readonly unknown[] | undefined {
  if (Array.isArray(value)) return value as readonly unknown[];
  if (ArrayBuffer.isView(value) && !(value instanceof DataView)) {
    return Array.from(value as unknown as ArrayLike<unknown>);
  }
  return undefined;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Delete mutation for a persisted annotation: just the annotation row. The
 * parent entity is pruned server-side when no stored row names it any more (the
 * backend is the only place that sees every row referencing the entity); the API delete opts in via `?prune_orphan_entity=true`. Kind-agnostic
 * — only the resource name comes from the kind's builder.
 */
export function buildDeleteMutations(
  annotation: LocalAnnotation,
  widgetId: string,
): ResourceMutation[] {
  const { resource } = payloadBuilderFor(annotation.kind);
  return [
    { op: "delete", resource, id: annotation.id, widgetId, localAnnotationId: annotation.id },
  ];
}

/**
 * What the delete gesture (Delete/Backspace, a trash button, a HUD's delete)
 * does to an annotation, so a control can say so before it is pressed: it
 * rejects a model's stored annotation — which deletes it — and deletes
 * anything else. Reject and delete send the same delete: the name tells the
 * reviewer that the row is a model's proposal.
 */
export type DeleteGesture = "delete" | "reject";

/**
 * What the delete gesture does to this annotation (`DeleteGesture`): `reject`
 * on a model's stored annotation, whatever its status (`isReviewable`),
 * `delete` on a person's annotation or a draft.
 *
 * @param annotation The annotation the gesture would act on.
 * @returns The gesture's effect.
 */
export function deleteGestureFor(annotation: LocalAnnotation): DeleteGesture {
  return isReviewable(annotation) ? "reject" : "delete";
}

/**
 * Kind-agnostic local delete, the one path every delete gesture takes — the
 * select tool's Delete/Backspace, the image widget's trash button, the 3D box
 * HUD: drops what the queue holds for the annotation, queues the backend
 * delete of a persisted one (`buildDeleteMutations`), then removes it from the
 * collection.
 *
 * A model's annotation is deleted like any other: that is its rejection
 * (`deleteGestureFor`). No row is left to mark it, so a later run of the model
 * may propose it again.
 *
 * What the queue holds for a stored row — its update, an entity a reassignment
 * queued for it — is dropped before the delete is queued, whoever made the
 * row: an edit of a row about to be deleted would only be sent to be undone,
 * and an entity made for it would be left named by nothing. A draft's creates
 * are dropped the same way, so it is never created only to be deleted.
 *
 * @param annotation The annotation the gesture acts on.
 * @param collection The store it lives in.
 * @param mutations The sink the delete is queued on.
 * @param widgetId Who acts, for the unsaved counters.
 * @param cancelGesture Cancels a gesture still under way where the delete was
 *   pressed — a resize, a drag — putting its shape back as stored and letting
 *   its staged work go. Called first: the delete then applies to the row as
 *   stored, and nothing half done is committed after it.
 */
export function deleteLocalAnnotation(
  annotation: LocalAnnotation,
  collection: AnnotationStore,
  mutations: MutationSink,
  widgetId: string,
  cancelGesture?: () => void,
): void {
  cancelGesture?.();
  mutations.dropForLocalAnnotation(annotation.id);
  if (annotation.persisted) {
    for (const m of buildDeleteMutations(annotation, widgetId)) mutations.queue(m);
  }
  collection.remove(annotation.id);
}

/**
 * The dependencies a draft-commit needs, satisfied as-is by `Scene2DContext`
 * (the 2D tool passes itself) and assembled from the manager by 3D widgets.
 */
export interface DraftCommitContext {
  readonly collection: AnnotationStore;
  readonly mutations: Pick<MutationSink, "queue">;
  readonly buildContext: BuildContext;
  readonly widgetId: string;
  /** Resolve an existing entity row for the annotation's label snapshot. */
  findEntity(entityId: string): Record<string, unknown> | undefined;
  /** Optional: nudge the renderer after the entity/label changes (2D). */
  requestRedraw?(): void;
}

/**
 * Kind-agnostic commit of a freshly drawn draft once the user has picked its
 * entity in the Inspector form: assign the entity (new id + snapshot, or link
 * an existing one), then queue the kind's create mutations. Mirrors
 * `deleteLocalAnnotation` so every drawable kind shares one commit path
 * instead of re-implementing it in its tool/widget.
 */
export function commitDraftWithEntity(
  annotation: LocalAnnotation,
  choice: PendingEntityChoice,
  ctx: DraftCommitContext,
): void {
  const builder = payloadBuilderFor(annotation.kind);

  if (choice.mode === "existing") {
    ctx.collection.setEntity(annotation.id, choice.entityId, ctx.findEntity(choice.entityId));
  } else {
    const entityId = generateShortId();
    ctx.collection.setEntity(annotation.id, entityId, { id: entityId, ...choice.entityFields });
  }

  // Re-read so the builder sees the just-assigned entityId.
  const committed = ctx.collection.find(annotation.id);
  if (!committed) return;

  const entityOpts =
    choice.mode === "existing" ? { linkExisting: true } : { entityFields: choice.entityFields };
  for (const m of builder.buildCreate(ctx.buildContext, committed, ctx.widgetId, entityOpts)) {
    ctx.mutations.queue(m);
  }
  ctx.requestRedraw?.();
}

/**
 * Dependencies for reassigning a *persisted* annotation's entity. Like
 * `DraftCommitContext` but the annotation mutation is an update (not a create),
 * so the queue must expose `upsertUpdate` too.
 */
export interface ReassignEntityContext {
  readonly collection: AnnotationStore;
  readonly mutations: Pick<
    MutationSink,
    "pending" | "queue" | "upsertUpdate" | "dropForLocalAnnotation" | "dropPendingEntityCreate"
  >;
  readonly buildContext: BuildContext;
  readonly widgetId: string;
  findEntity(entityId: string): Record<string, unknown> | undefined;
  requestRedraw?(): void;
}

/**
 * Kind-agnostic reassignment of an existing annotation's entity: point it at a
 * different entity (an existing one, or a freshly created one), then queue the
 * annotation update carrying the new `entity_id`. The previously attached
 * entity is pruned server-side when no stored row names it any more — the
 * update is sent with `?prune_orphan_entity=true` (see `updateAnnotation`).
 * Mirrors `commitDraftWithEntity` for the edit lifecycle.
 */
export function reassignEntity(
  annotation: LocalAnnotation,
  choice: PendingEntityChoice,
  ctx: ReassignEntityContext,
): void {
  if (!annotation.persisted) return;

  // Whatever this choice turns out to be, it supersedes the previous one: any
  // entity still queued for this annotation is now unreachable, since
  // `upsertUpdate` leaves only the latest choice referenced. Dropped before the
  // branch, not inside it — landing on an *existing* entity abandons a
  // previously typed one just as surely as typing another name does, and
  // guarding only the second case still wrote the orphan to the dataset.
  ctx.mutations.dropPendingEntityCreate(annotation.id);

  if (choice.mode === "existing") {
    ctx.collection.setEntity(annotation.id, choice.entityId, ctx.findEntity(choice.entityId));
  } else {
    const entityId = generateShortId();
    ctx.collection.setEntity(annotation.id, entityId, { id: entityId, ...choice.entityFields });
    ctx.mutations.queue(
      buildEntityCreateMutation(
        ctx.buildContext,
        entityId,
        choice.entityFields,
        ctx.widgetId,
        annotation.id,
      ),
    );
  }

  // Re-read so the update body carries the just-assigned entityId.
  const updated = ctx.collection.find(annotation.id);
  if (!updated) return;

  queueContentEdit(ctx, updated);
  ctx.requestRedraw?.();
}

/** What `beginEntityReassign` needs on top of the reassignment itself. */
export interface EntityReassignContext extends ReassignEntityContext {
  beginPendingAnnotation(pending: PendingAnnotation): void;
}

export interface BeginEntityReassignOptions {
  /** Header shown above the entity form, e.g. "box entity". */
  label: string;
}

/**
 * Bring the annotation's payload in line with the chosen entity, for a kind
 * that declares `geometryForEntity`. Returns whether the move should go ahead.
 *
 * **Applies the change by writing to the collection.** The write is the
 * mechanism: `reassignEntity` re-reads the live annotation to build its update
 * body, precisely so that body carries the entity id just assigned.
 */
function alignPayloadWithEntity(
  annotation: LocalAnnotation,
  choice: PendingEntityChoice,
  ctx: EntityReassignContext,
): boolean {
  const builder = payloadBuilderFor(annotation.kind);
  if (!builder.geometryForEntity) return true;

  const entity = choice.mode === "new" ? choice.entityFields : ctx.findEntity(choice.entityId);
  const geometry = builder.geometryForEntity(annotation, entity);
  if (geometry === null) return false;

  ctx.collection.setGeometry(annotation.id, geometry);
  return true;
}

/**
 * Ask for an entity, then move the annotation onto it — the whole "this shape
 * belongs to something else" flow, in one kind-agnostic place.
 *
 * Every kind reaches it the same way: the widget toolbar for 2D shapes, the box
 * HUD in 3D, a double-click on a classification chip. They differ only in how
 * the user gets here, never in what happens next, which is why the guard, the
 * form call and the commit live together rather than being re-typed per kind.
 *
 * Drafts are refused on purpose. An annotation that has never reached the
 * backend has no entity to move away from — its entity is still being chosen by
 * the create flow (`commitDraftWithEntity`), and letting a second picker run
 * alongside it would queue two entities for one shape.
 */
export function beginEntityReassign(
  annotation: LocalAnnotation,
  ctx: EntityReassignContext,
  opts: BeginEntityReassignOptions,
): void {
  if (!annotation.persisted) return;

  ctx.beginPendingAnnotation({
    label: opts.label,
    onConfirm: (choice) => {
      if (!alignPayloadWithEntity(annotation, choice, ctx)) return;
      reassignEntity(annotation, choice, ctx);
    },
    // Nothing to undo: unlike creation there is no draft waiting on this
    // answer, so cancelling leaves the annotation exactly as it was.
    onCancel: () => ctx.requestRedraw?.(),
  });
}
