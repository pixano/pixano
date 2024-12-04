/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export type PolygonGroupPoint = {
  x: number;
  y: number;
  id: number;
};

export type PolygonShape = {
  simplifiedSvg: string[];
  simplifiedPoints: PolygonGroupPoint[][];
};
