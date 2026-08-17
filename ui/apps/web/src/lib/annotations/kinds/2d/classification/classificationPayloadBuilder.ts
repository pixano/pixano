/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ClassificationGeometry } from "./classificationTypes.js";
import type { LocalAnnotation } from "$lib/annotations/annotationCollection.svelte.js";
import {
  buildCreateMutations,
  DEFAULT_SOURCE,
  generateShortId,
  type BuildAnnotationOpts,
  type BuildAnnotationResult,
  type BuildContext,
  type EntityCreateChoice,
} from "$lib/annotations/buildPayloads.js";
import type { ResourceMutation } from "$lib/annotations/types.js";

/** Backend table this kind writes to. Owned here — nothing else declares it. */
export const CLASSIFICATION_RESOURCE = "classifications";

/**
 * Body for a classification, shared by create and update.
 *
 * **This kind does not carry the frame linkage.** `Classification` extends
 * `EntityAnnotation`, not `PerFrameAnnotation` (unlike BBox, CompressedRLE,
 * KeyPoints and MultiPath), so it has no `frame_id`, `frame_index`,
 * `tracklet_id` or `entity_dynamic_state_id` columns — sending them would be
 * rejected as unknown fields. That is why `singleFrameLinkage` is deliberately
 * absent from `buildClassificationCreate` below.
 *
 * With no extra create-only columns, create and update share one body, which
 * satisfies invariant D9 by construction.
 */
export function buildClassificationBody(
  ctx: BuildContext,
  classificationId: string,
  entityId: string,
  geometry: ClassificationGeometry,
): Record<string, unknown> {
  return {
    id: classificationId,
    record_id: ctx.recordId,
    entity_id: entityId,
    view_id: ctx.viewId,
    labels: [...geometry.labels],
    confidences: [...geometry.confidences],
    ...DEFAULT_SOURCE,
  };
}

/** The (entity, classification) create mutation pair. */
export function buildClassificationCreate(
  ctx: BuildContext,
  geometry: ClassificationGeometry,
  opts: BuildAnnotationOpts = {},
): BuildAnnotationResult {
  const entityId = opts.entityId ?? generateShortId();
  const annotationId = opts.annotationId ?? generateShortId();
  const body = buildClassificationBody(ctx, annotationId, entityId, geometry);

  return {
    entityId,
    annotationId,
    mutations: buildCreateMutations(
      ctx,
      CLASSIFICATION_RESOURCE,
      { entityId, annotationId },
      body,
      opts,
    ),
  };
}

/**
 * Payload knowledge for media-level classifications. The first kind with no
 * spatial payload — which the write path handles unchanged, since
 * `commitNewAnnotation` / `commitGeometryEdit` are generic over the payload
 * type and never inspect it.
 */
export const classificationPayloadBuilder = {
  kind: "classification" as const,
  resource: CLASSIFICATION_RESOURCE,

  buildCreate(
    ctx: BuildContext,
    annotation: LocalAnnotation<ClassificationGeometry>,
    widgetId: string,
    entity: EntityCreateChoice = {},
  ): ResourceMutation[] {
    return buildClassificationCreate(ctx, annotation.geometry, {
      widgetId,
      localAnnotationId: annotation.id,
      entityId: annotation.entityId,
      annotationId: annotation.id,
      entityFields: entity.entityFields,
      linkExisting: entity.linkExisting,
    }).mutations;
  },

  buildUpdate(
    ctx: BuildContext,
    annotation: LocalAnnotation<ClassificationGeometry>,
  ): Record<string, unknown> {
    return buildClassificationBody(ctx, annotation.id, annotation.entityId, annotation.geometry);
  },
};
