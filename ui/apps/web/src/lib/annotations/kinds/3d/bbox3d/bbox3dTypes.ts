/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** Id of the 3D box draw/edit tool — shared so the tool def and its overlay
 * can reference it without importing each other. */
export const DRAW_BBOX3D_TOOL_ID = "draw-bbox3d";

export interface BBoxRenderData {
  id: string;
  position: [number, number, number];
  size: [number, number, number];
  /** Plain XYZW components — avoids a THREE import in the Widget. */
  quaternion: { x: number; y: number; z: number; w: number };
  label?: string;
}

export interface GizmoVisibility {
  rings: boolean;
  resizeArrows: boolean;
  translateArrows: boolean;
}
