export type PolygonGroupPoint = {
  x: number;
  y: number;
  id: number;
};

export type PolygonGroupStatus = "created" | "creating";

export type PolygonGroupDetails = {
  points: PolygonGroupPoint[];
  visible: boolean;
  editing: boolean;
  status: PolygonGroupStatus;
  id: string;
};
