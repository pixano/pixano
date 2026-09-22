/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Geometry of a segmentation mask, held exactly as the backend serves it.
 *
 * `counts` stays in its COCO run-length *string* form rather than the decoded
 * `number[]`: it is what `MaskCreate`/`MaskResponse` carry over the wire (the
 * backend serializes `bytes` to a utf-8 string, see
 * `CompressedRLE._serialize_counts`), so the payload builder and the seed
 * loader move it through untouched and only the raster layer decodes it.
 *
 * Unlike a bbox — normalized to [0,1] so it survives a display resize — a mask
 * is inherently tied to the pixel grid it was painted on, so `size` travels
 * with it and the renderer scales the raster onto whatever frame the image
 * currently occupies.
 */
export interface MaskGeometry {
  /** `[height, width]` of the image grid the RLE indexes into. */
  size: [number, number];
  /** COCO-style run-length encoding, in the backend's string form. */
  counts: string;
}

/** Konva node name for a mask raster, shared by the renderer and its tests. */
export const MASK_NODE_NAME = "pixano-mask";

/** Attribute carrying the local annotation id on a mask node. */
export const MASK_ID_ATTR = "pixanoMaskId";

/** Tool id of the brush, referenced by the toolbar and by tests. */
export const DRAW_MASK_TOOL_ID = "draw-mask";

/**
 * Tool id of the prompt-driven segmenter. A second tool over the same kind:
 * the brush and the model both produce an ordinary mask, they only differ in
 * how the region is described.
 */
export const SMART_SEGMENT_TOOL_ID = "smart-segment";
