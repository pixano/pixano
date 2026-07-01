/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { BBox3DGeometry, LocalAnnotation } from "$lib/annotations/annotationCollection.svelte.js";
import {
  buildBBox3DCreate,
  buildBBox3DUpdate,
  type BuildContext,
  type EntityCreateChoice,
} from "$lib/annotations/buildPayloads.js";
import type { ResourceMutation } from "$lib/annotations/types.js";
import { BBOX3D_RESOURCE } from "$lib/api/resourceNames.js";

export { BBOX3D_RESOURCE };

/**
 * Payload knowledge for 3D boxes. The local annotation id doubles as the
 * backend row id (see bboxPayloadBuilder); editor output is always xyzwhd,
 * which is what the backend update model expects.
 */
export const bbox3dPayloadBuilder = {
  kind: "bbox3d" as const,
  resource: BBOX3D_RESOURCE,

  buildCreate(
    ctx: BuildContext,
    annotation: LocalAnnotation<BBox3DGeometry>,
    widgetId: string,
    entity: EntityCreateChoice = {},
  ): ResourceMutation[] {
    return buildBBox3DCreate(ctx, annotation.geometry.coords, {
      widgetId,
      localAnnotationId: annotation.id,
      entityId: annotation.entityId,
      bboxId: annotation.id,
      rotation: annotation.geometry.rotation,
      entityFields: entity.entityFields,
      linkExisting: entity.linkExisting,
    }).mutations;
  },

  buildUpdate(
    ctx: BuildContext,
    annotation: LocalAnnotation<BBox3DGeometry>,
  ): Record<string, unknown> {
    return buildBBox3DUpdate(
      ctx,
      annotation.id,
      annotation.entityId,
      annotation.geometry.coords,
      annotation.geometry.rotation,
    );
  },
};
