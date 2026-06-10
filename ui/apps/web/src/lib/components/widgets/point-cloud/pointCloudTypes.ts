/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

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
