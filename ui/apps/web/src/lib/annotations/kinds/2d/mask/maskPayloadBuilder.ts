/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MaskGeometry } from "./maskTypes.js";
import type { LocalAnnotation } from "$lib/annotations/annotationCollection.svelte.js";
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
import type { ResourceMutation } from "$lib/annotations/types.js";

/** Backend table this kind writes to. Owned here — nothing else declares it. */
export const MASK_RESOURCE = "masks";

/**
 * Update body for a mask. Matches the backend `MaskUpdate` transport model,
 * built from `CompressedRLE` — which notably has **no `confidence` column**
 * (unlike BBox), so sending one would be rejected as an unknown field.
 *
 * INVARIANT (D9): `buildCreate`'s body must be a superset of this one with
 * identical values outside the geometry, so `commitGeometryEdit` can patch a
 * still-pending create with it.
 */
export function buildMaskUpdate(
  ctx: BuildContext,
  maskId: string,
  entityId: string,
  geometry: MaskGeometry,
): Record<string, unknown> {
  return {
    id: maskId,
    record_id: ctx.recordId,
    entity_id: entityId,
    view_id: ctx.viewId,
    size: Array.from(geometry.size),
    counts: geometry.counts,
    ...DEFAULT_SOURCE,
  };
}

/** The (entity, mask) create mutation pair for a newly painted mask. */
export function buildMaskCreate(
  ctx: BuildContext,
  geometry: MaskGeometry,
  opts: BuildAnnotationOpts = {},
): BuildAnnotationResult {
  const entityId = opts.entityId ?? generateShortId();
  const annotationId = opts.annotationId ?? generateShortId();

  const body: Record<string, unknown> = {
    ...buildMaskUpdate(ctx, annotationId, entityId, geometry),
    ...singleFrameLinkage(ctx),
  };

  return {
    entityId,
    annotationId,
    mutations: buildCreateMutations(ctx, MASK_RESOURCE, { entityId, annotationId }, body, opts),
  };
}

/**
 * Payload knowledge for segmentation masks. The local annotation id doubles as
 * the backend row id, as for every other kind, so a freshly painted mask can be
 * updated or deleted once its create has been flushed.
 */
export const maskPayloadBuilder = {
  kind: "mask" as const,
  resource: MASK_RESOURCE,

  buildCreate(
    ctx: BuildContext,
    annotation: LocalAnnotation<MaskGeometry>,
    widgetId: string,
    entity: EntityCreateChoice = {},
  ): ResourceMutation[] {
    return buildMaskCreate(ctx, annotation.geometry, {
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
    annotation: LocalAnnotation<MaskGeometry>,
  ): Record<string, unknown> {
    return buildMaskUpdate(ctx, annotation.id, annotation.entityId, annotation.geometry);
  },
};
