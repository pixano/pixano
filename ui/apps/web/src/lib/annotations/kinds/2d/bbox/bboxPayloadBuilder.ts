/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  BBoxGeometry,
  LocalAnnotation,
} from "$lib/annotations/annotationCollection.svelte.js";
import {
  buildCreateMutations,
  DEFAULT_SOURCE,
  generateShortId,
  singleFrameLinkage,
  type BuildAnnotationOpts,
  type BuildAnnotationResult,
  type BuildContext,
  type EntityCreateChoice,
} from "$lib/annotations/buildPayloads.js";
import type { CoordsNorm, ResourceMutation } from "$lib/annotations/types.js";

/** Backend table this kind writes to. Owned here — nothing else declares it. */
export const BBOX_RESOURCE = "bboxes";

/**
 * Update body for a 2D box. Only the fields the backend's `BBoxUpdate`
 * transport model accepts (see `src/pixano/api/models.py`); the server merges
 * this onto the existing row.
 *
 * INVARIANT (D9): `buildCreate`'s body must be a superset of this one with
 * identical values outside the geometry, so `commitGeometryEdit` can patch a
 * still-pending create with it.
 */
export function buildBBoxUpdate(
  ctx: BuildContext,
  bboxId: string,
  entityId: string,
  coordsNorm: CoordsNorm,
): Record<string, unknown> {
  return {
    id: bboxId,
    record_id: ctx.recordId,
    entity_id: entityId,
    view_id: ctx.viewId,
    coords: Array.from(coordsNorm),
    format: "xywh",
    is_normalized: true,
    confidence: 1,
    ...DEFAULT_SOURCE,
  };
}

/**
 * The (entity, bbox) create mutation pair for a new 2D box.
 *
 * Entities carry only `{ id, record_id, parent_id }` plus user fields — the
 * `Entity` schema declares no source_* or timestamp columns and LanceModel
 * tables reject unknown ones. The box itself carries the full per-frame
 * annotation shape.
 */
export function buildBBoxCreate(
  ctx: BuildContext,
  coordsNorm: CoordsNorm,
  opts: BuildAnnotationOpts = {},
): BuildAnnotationResult {
  const entityId = opts.entityId ?? generateShortId();
  const annotationId = opts.annotationId ?? generateShortId();

  const body: Record<string, unknown> = {
    ...buildBBoxUpdate(ctx, annotationId, entityId, coordsNorm),
    ...singleFrameLinkage(ctx),
  };

  return {
    entityId,
    annotationId,
    mutations: buildCreateMutations(ctx, BBOX_RESOURCE, { entityId, annotationId }, body, opts),
  };
}

/**
 * Payload knowledge for 2D boxes. The local annotation id doubles as the
 * backend row id so a freshly drawn box can be updated or deleted after its
 * create has been flushed.
 */
export const bboxPayloadBuilder = {
  kind: "bbox" as const,
  resource: BBOX_RESOURCE,

  buildCreate(
    ctx: BuildContext,
    annotation: LocalAnnotation<BBoxGeometry>,
    widgetId: string,
    entity: EntityCreateChoice = {},
  ): ResourceMutation[] {
    return buildBBoxCreate(ctx, annotation.geometry, {
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
    annotation: LocalAnnotation<BBoxGeometry>,
  ): Record<string, unknown> {
    return buildBBoxUpdate(ctx, annotation.id, annotation.entityId, annotation.geometry);
  },
};
