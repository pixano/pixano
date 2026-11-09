/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { BBoxRenderData } from "./bbox3dTypes.js";
import type { LocalBBox3DAnnotation } from "$lib/annotations/annotationCollection.svelte.js";
import { bboxTransform } from "$lib/annotations/coordinateTransforms";
import { pickEntityLabel } from "$lib/annotations/types.js";

/**
 * A stored 3D box as the box editor takes it: its place, size and turn in
 * three.js space, and its entity's label — so the editor stays free of the
 * dataset's formats. The one way a box reaches the editor (`BBox3DTool` builds
 * the editor's list with it), which the session counts on: a box opened and
 * saved untouched comes back from the editor as this trip makes it.
 */
export function editorBoxOf(annotation: LocalBBox3DAnnotation): BBoxRenderData {
  const { position, size, quaternion } = bboxTransform(annotation.geometry);
  return {
    id: annotation.id,
    position,
    size,
    quaternion: { x: quaternion.x, y: quaternion.y, z: quaternion.z, w: quaternion.w },
    label: pickEntityLabel(annotation.entity),
  };
}
