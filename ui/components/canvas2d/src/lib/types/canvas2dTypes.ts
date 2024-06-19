export type PolygonGroupPoint = {
  x: number;
  y: number;
  id: number;
};

export type PolygonShape = {
  simplifiedSvg: string[];
  simplifiedPoints: PolygonGroupPoint[][];
};