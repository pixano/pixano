import type { KeyPointsTemplate } from "@pixano/core";

const face: KeyPointsTemplate = {
  id: "face",
  vertices: [
    {
      x: 0.3,
      y: 0.1,
      features: {
        label: "eye left",
        color: "blue",
      },
    },
    {
      x: 0.6,
      y: 0.1,
      features: {
        label: "eye right",
        color: "blue",
      },
    },
    {
      x: 0.45,
      y: 0.3,
      features: {
        label: "nose",
        color: "green",
      },
    },
    {
      x: 0.45,
      y: 0.6,
      features: {
        label: "mouth",
        color: "red",
      },
    },
  ],
  edges: [
    [0, 2],
    [1, 2],
    [2, 3],
  ],
};

const car: KeyPointsTemplate = {
  id: "person",
  vertices: [
    {
      x: 0.5,
      y: 0.1,
      features: {
        label: "head",
        state: "visible",
      },
    },
    {
      x: 0.5,
      y: 0.4,
      features: {
        label: "middle",
        state: "visible",
      },
    },
    {
      x: 0.3,
      y: 0.4,
      features: {
        label: "left arm",
        state: "visible",
      },
    },
    {
      x: 0.7,
      y: 0.4,
      features: {
        label: "right arm",
        state: "visible",
      },
    },
    {
      x: 0.5,
      y: 0.7,
      features: {
        label: "belly",
        state: "visible",
      },
    },
    {
      x: 0.3,
      y: 0.9,
      features: {
        label: "left foot",
        state: "visible",
      },
    },
    {
      x: 0.7,
      y: 0.9,
      features: {
        label: "right foot",
        state: "visible",
      },
    },
  ],
  edges: [
    [0, 1],
    [1, 2],
    [1, 3],
    [1, 4],
    [4, 5],
    [4, 6],
  ],
};

export const templates: KeyPointsTemplate[] = [face, car];
