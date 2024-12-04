/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { KeypointsTemplate } from "@pixano/core";

export const findRectBoundaries = (vertices: KeypointsTemplate["vertices"]) => {
  const x = Math.min(...vertices.map((point) => point.x));
  const y = Math.min(...vertices.map((point) => point.y));
  const width = Math.max(...vertices.map((point) => point.x)) - x;
  const height = Math.max(...vertices.map((point) => point.y)) - y;
  return { x, y, width, height };
};
