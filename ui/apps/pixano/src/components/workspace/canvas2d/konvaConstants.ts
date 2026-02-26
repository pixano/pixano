/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const INPUTRECT_STROKEWIDTH: number = 1.5;
export const BBOX_STROKEWIDTH: number = 2.0;

// Draft shape colors (shared across CreatePolygon, CreateRectangle, PolygonVertices)
export const DRAFT_LINE_COLOR = "hsl(330, 65%, 50%)";
export const DRAFT_FILL_COLOR = "hsla(330, 60%, 95%, 0.2)";
export const DRAFT_RECT_FILL_COLOR = "hsla(330, 60%, 95%, 0.45)";
export const FIRST_VERTEX_COLOR = "hsl(330, 65%, 50%)";
export const OTHER_VERTEX_COLOR = "hsl(142, 60%, 40%)";

// Brush
export const BRUSH_MASK_COLOR = "rgba(255, 0, 80, 0.5)";

// Interaction thresholds
export const EDGE_SNAP_PX = 8;
export const INTERACTION_COOLDOWN_MS = 120;
export const FILTER_DEBOUNCE_MS = 50;
