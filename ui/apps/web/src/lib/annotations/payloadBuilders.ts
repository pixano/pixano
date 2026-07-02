/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ENTITY_RESOURCE } from "$lib/api/resourceNames.js";

import type {
  AnnotationKind,
  AnnotationStore,
  LocalAnnotation,
} from "./annotationCollection.svelte.js";
import { generateShortId, type BuildContext } from "./buildPayloads.js";
import { bboxPayloadBuilder } from "./kinds/2d/bbox/bboxPayloadBuilder.js";
import { bbox3dPayloadBuilder } from "./kinds/3d/bbox3d/bbox3dPayloadBuilder.js";
import type { MutationSink } from "./scene/sceneContext.js";
import type { ResourceMutation } from "./types.js";

/**
 * Per-kind knowledge of how a `LocalAnnotation` becomes backend payloads.
 * One entry per kind in `PAYLOAD_BUILDERS`; nothing outside the kind's
 * module knows its resource name or body shape.
 */
export interface PayloadBuilder<G = unknown> {
  kind: AnnotationKind;
  /** Backend collection name, e.g. "bboxes". */
  resource: string;
  /** Mutations creating the annotation and its parent entity. */
  buildCreate(ctx: BuildContext, annotation: LocalAnnotation<G>, widgetId: string): ResourceMutation[];
  /** Update body for an existing annotation whose geometry changed. */
  buildUpdate(ctx: BuildContext, annotation: LocalAnnotation<G>): Record<string, unknown>;
}

const PAYLOAD_BUILDERS: ReadonlyMap<AnnotationKind, PayloadBuilder> = new Map<
  AnnotationKind,
  PayloadBuilder
>([
  [bboxPayloadBuilder.kind, bboxPayloadBuilder as PayloadBuilder],
  [bbox3dPayloadBuilder.kind, bbox3dPayloadBuilder as PayloadBuilder],
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
export function commitGeometryEdit<G>(
  ctx: CommitContext,
  annotationId: string,
  geometry: G,
): void {
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
 * Delete mutations for a persisted annotation: the annotation row plus its
 * parent entity. Kind-agnostic — only the resource name comes from the
 * kind's builder.
 */
export function buildDeleteMutations(
  annotation: LocalAnnotation,
  widgetId: string,
): ResourceMutation[] {
  const { resource } = payloadBuilderFor(annotation.kind);
  return [
    { op: "delete", resource, id: annotation.id, widgetId, localAnnotationId: annotation.id },
    {
      op: "delete",
      resource: ENTITY_RESOURCE,
      id: annotation.entityId,
      widgetId,
      localAnnotationId: annotation.id,
    },
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
