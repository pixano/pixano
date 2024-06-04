export type PolygonGroupPoint = {
  x: number;
  y: number;
  id: number;
};

export type PolygonShape = {
  simplifiedSvg: string[];
  simplifiedPoints: PolygonGroupPoint[][];
};

export type Filters = {
  brightness: number;
  contrast: number;
  equalizeHistogram: boolean;
  redRange: number[];
  greenRange: number[];
  blueRange: number[];
};
