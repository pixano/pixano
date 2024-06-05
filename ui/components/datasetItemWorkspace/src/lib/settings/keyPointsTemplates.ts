import type { KeyPointsTemplate } from "@pixano/core";

export const templates: KeyPointsTemplate[] = [
  {
    id: "face",
    vertices: [
      {
        x: 0.3,
        y: 0.1,
        features: ["eye left"],
      },
      {
        x: 0.6,
        y: 0.1,
        features: ["eye right"],
      },
      {
        x: 0.45,
        y: 0.3,
        features: ["nose"],
      },
      {
        x: 0.45,
        y: 0.6,
        features: ["mouth"],
      },
    ],
    edges: [
      [0, 2],
      [1, 2],
      [2, 3],
    ],
  },
];
