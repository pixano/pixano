export type PolygonGroupPoint = {
  x: number;
  y: number;
  id: number;
};

export type PolygonGroupStatus = "created" | "creating";

export type PolygonGroupDetails = {
  points: PolygonGroupPoint[];
  visible: boolean;
  status: PolygonGroupStatus;
};
