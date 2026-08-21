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
 * collection, then either queue an update (persisted) or patch its still-pending
 * create (draft). Kind-agnostic — the body comes from the kind's `buildUpdate`,
 * which is a superset of the create body's geometry fields, so patching a
 * pending create with it only changes the geometry.
 */
export function commitGeometryEdit<G>(ctx: CommitContext, annotationId: string, geometry: G): void {
  const annotation = ctx.collection.find(annotationId);
  if (!annotation) return;
  ctx.collection.setGeometry(annotationId, geometry);

  const builder = payloadBuilderFor(annotation.kind);
  const body = builder.buildUpdate(ctx.buildContext, annotation);
  if (annotation.persisted) {
    ctx.mutations.upsertUpdate({
      op: "update",
      resource: builder.resource,
      id: annotation.id,
      body,
      widgetId: ctx.widgetId,
      localAnnotationId: annotation.id,
    });
  } else {
    // INVARIANT (D9): the create body must be a superset of `buildUpdate`'s
    // fields, with identical values for everything except geometry. Then merging
    // this body into the queued create changes only the geometry. A future kind
    // whose buildUpdate diverges from buildCreate on a shared field would break
    // this — keep them aligned (covered by commit.test.ts).
    ctx.mutations.patchPendingCreate(annotation.id, builder.resource, body);
  }
}

/**
 * Delete mutation for a persisted annotation: just the annotation row. The
 * parent entity is pruned server-side when this was its last annotation (the
 * backend is the only place that sees every annotation referencing the
 * entity); the API delete opts in via `?prune_orphan_entity=true`. Kind-agnostic
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
 * Kind-agnostic local delete: queues the backend deletes for a persisted
 * annotation, or drops the not-yet-flushed creates for a draft, then removes
 * it from the collection. Used by select tools and widget delete buttons.
 */
export function deleteLocalAnnotation(
  annotation: LocalAnnotation,
  collection: AnnotationStore,
  mutations: MutationSink,
  widgetId: string,
): void {
  if (annotation.persisted) {
    for (const m of buildDeleteMutations(annotation, widgetId)) mutations.queue(m);
  } else {
    mutations.dropForLocalAnnotation(annotation.id);
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
  readonly mutations: Pick<MutationSink, "queue" | "upsertUpdate" | "dropPendingEntityCreate">;
  readonly buildContext: BuildContext;
  readonly widgetId: string;
  findEntity(entityId: string): Record<string, unknown> | undefined;
  requestRedraw?(): void;
}

/**
 * Kind-agnostic reassignment of an existing annotation's entity: point it at a
 * different entity (an existing one, or a freshly created one), then queue the
 * annotation update carrying the new `entity_id`. The previously attached
 * entity is pruned server-side when this leaves it with no annotations — the
 * update is sent with `?prune_orphan_entity=true` (see `updateAnnotation`).
 * Mirrors `commitDraftWithEntity` for the edit lifecycle.
 */
export function reassignEntity(
  annotation: LocalAnnotation,
  choice: PendingEntityChoice,
  ctx: ReassignEntityContext,
): void {
  if (!annotation.persisted) return;
  const builder = payloadBuilderFor(annotation.kind);

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

  ctx.mutations.upsertUpdate({
    op: "update",
    resource: builder.resource,
    id: annotation.id,
    body: builder.buildUpdate(ctx.buildContext, updated),
    widgetId: ctx.widgetId,
    localAnnotationId: annotation.id,
  });
  ctx.requestRedraw?.();
}

/** What `beginEntityReassign` needs on top of the reassignment itself. */
export interface EntityReassignContext extends ReassignEntityContext {
  beginPendingAnnotation(pending: PendingAnnotation): void;
}

export interface BeginEntityReassignOptions {
  /** Header shown above the entity form, e.g. "box entity". */
  label: string;
  /**
   * Last chance for a kind to bring its own payload in line with the chosen
   * entity before the reassignment is queued. Returning `null` aborts.
   *
   * Exists for one real case: a classification's labels *are* the entity's
   * label, so moving it to another entity without rewriting them would leave a
   * chip asserting a class the annotation no longer belongs to. Every other
   * kind carries geometry independent of its entity and needs nothing here.
   */
  adapt?: (annotation: LocalAnnotation, choice: PendingEntityChoice) => LocalAnnotation | null;
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
      const adapted = opts.adapt ? opts.adapt(annotation, choice) : annotation;
      if (!adapted) return;
      reassignEntity(adapted, choice, ctx);
    },
    // Nothing to undo: unlike creation there is no draft waiting on this
    // answer, so cancelling leaves the annotation exactly as it was.
    onCancel: () => ctx.requestRedraw?.(),
  });
}
