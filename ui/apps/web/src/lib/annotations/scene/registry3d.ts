/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { MousePointer2 } from "lucide-svelte";

import BBox3DRenderer from "../kinds/3d/bbox3d/BBox3DRenderer.svelte";
import { drawBBox3DTool } from "../kinds/3d/bbox3d/drawBBox3DTool.js";
import type { AnnotationRenderer3DFactory } from "./renderer.js";
import { DEFAULT_TOOL_3D, type Tool3D } from "./tool.js";

/** Default 3D tool: orbit/pan the camera, no annotation interaction. */
const navigateTool3D: Tool3D = {
  id: DEFAULT_TOOL_3D,
  label: "Navigate",
  icon: MousePointer2,
};

/**
 * Every 3D tool, in toolbar order. Adding a 3D annotation kind means adding
 * its tool import here — widgets render their toolbar from this list and
 * never reference individual tools.
 */
export const TOOLS_3D: readonly Tool3D[] = [navigateTool3D, drawBBox3DTool];

/**
 * Every 3D renderer; the scene mounts one component per entry. Adding a 3D kind
 * means adding its renderer here — the scene never references a kind directly.
 */
export const RENDERER_FACTORIES_3D: readonly AnnotationRenderer3DFactory[] = [
  { kind: "bbox3d", component: BBox3DRenderer },
];

export { DEFAULT_TOOL_3D } from "./tool.js";
