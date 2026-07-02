/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * The Konva node-identity contract for the "bbox" kind: the renderer stamps
 * these onto each rect (`name` + a `bboxId` attr) and the editor finds nodes by
 * them. Shared here so display (`bboxRenderer2D`) and input (`bboxEditor2D`)
 * never drift — a rename in one would otherwise silently break the other with no
 * compile error.
 */
export const BBOX_NODE_NAME = "bbox";
export const BBOX_ID_ATTR = "bboxId";
