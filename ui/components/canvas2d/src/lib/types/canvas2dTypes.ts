import type { MaskSVG } from "@pixano/core";

export type PolygonGroupPoint = {
  x: number;
  y: number;
  id: number;
};

export type PolygonGroupStatus = "created" | "creating";

export type PolygonGroupDetails = {
  points: PolygonGroupPoint[];
  svg: MaskSVG;
  visible: boolean;
  editing: boolean;
  status: PolygonGroupStatus;
  id: string;
};
