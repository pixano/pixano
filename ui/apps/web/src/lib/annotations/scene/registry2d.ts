/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { bboxRenderer2DFactory } from "../kinds/2d/bbox/bboxRenderer2D.js";
import { drawBBoxTool } from "../kinds/2d/bbox/drawBBoxTool.js";
import { bbox3dRenderer2DFactory } from "../kinds/2d/bbox3d/bbox3dRenderer2D.js";
import { drawKeypointsTool } from "../kinds/2d/keypoints/drawKeypointsTool.js";
import { keypointsRenderer2DFactory } from "../kinds/2d/keypoints/keypointsRenderer2D.js";
import { drawMaskTool } from "../kinds/2d/mask/drawMaskTool.js";
import { maskRenderer2DFactory } from "../kinds/2d/mask/maskRenderer2D.js";
import { smartSegmentTool } from "../kinds/2d/mask/smartSegmentTool.js";
import type { AnnotationRenderer2DFactory } from "./renderer.js";
import { selectTool2D } from "./selectTool2D.js";
import type { Tool2D } from "./tool.js";

/**
 * Every 2D tool, in toolbar order. Adding an annotation kind means adding
 * its tool import here — widgets render their toolbar from this list and
 * never reference individual tools.
 */
export const TOOLS_2D: readonly Tool2D[] = [
  selectTool2D,
  drawBBoxTool,
  drawMaskTool,
  smartSegmentTool,
  drawKeypointsTool,
];

/** Every 2D renderer factory; widgets instantiate one renderer per kind. */
export const RENDERER_FACTORIES_2D: readonly AnnotationRenderer2DFactory[] = [
  bboxRenderer2DFactory,
  bbox3dRenderer2DFactory,
  maskRenderer2DFactory,
  keypointsRenderer2DFactory,
];

export { DEFAULT_TOOL_2D } from "./tool.js";

export function getTool2D(id: string): Tool2D | undefined {
  return TOOLS_2D.find((tool) => tool.id === id);
}
