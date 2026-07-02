/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { BBoxGeometry, LocalAnnotation } from "$lib/annotations/annotationCollection.svelte.js";
import { buildBBoxCreate, buildBBoxUpdate, type BuildContext } from "$lib/annotations/buildPayloads.js";
import type { ResourceMutation } from "$lib/annotations/types.js";
import { BBOX_RESOURCE } from "$lib/api/resourceNames.js";

export { BBOX_RESOURCE };

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
  ): ResourceMutation[] {
    return buildBBoxCreate(ctx, annotation.geometry, {
      widgetId,
      localAnnotationId: annotation.id,
      entityId: annotation.entityId,
      bboxId: annotation.id,
    }).mutations;
  },

  buildUpdate(ctx: BuildContext, annotation: LocalAnnotation<BBoxGeometry>): Record<string, unknown> {
    return buildBBoxUpdate(ctx, annotation.id, annotation.entityId, annotation.geometry);
  },
};
