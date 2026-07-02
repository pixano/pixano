/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Box } from "lucide-svelte";

import type { Tool3D } from "$lib/annotations/scene/tool.js";

import BBox3DHud from "./BBox3DHud.svelte";
import BBox3DTool from "./BBox3DTool.svelte";
import { BBox3DSession } from "./bbox3dSession.svelte.js";
import { DRAW_BBOX3D_TOOL_ID } from "./bbox3dTypes.js";

/**
 * The complete bbox3d draw/edit tool, all kind-owned (the host names no kind):
 *  - `overlay` (`BBox3DTool.svelte`): the in-canvas editor + transient preview.
 *  - `createSession` (`BBox3DSession`): per-widget confirm state, gizmo state, commit.
 *  - `hud` (`BBox3DHud.svelte`): the DOM confirm panel + gizmo toggles.
 * Clicking empty space places a new box; clicking an existing box edits it.
 */
export const drawBBox3DTool: Tool3D = {
  id: DRAW_BBOX3D_TOOL_ID,
  label: "Draw 3D box",
  icon: Box,
  kind: "bbox3d",
  cursor: "crosshair",
  overlay: BBox3DTool,
  hud: BBox3DHud,
  createSession: (seam) => new BBox3DSession(seam),
};
