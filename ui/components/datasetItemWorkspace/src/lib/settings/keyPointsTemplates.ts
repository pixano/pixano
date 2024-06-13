import type { KeypointsTemplate } from "@pixano/core";

const face: KeypointsTemplate = {
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

const person: KeypointsTemplate = {
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

const cow: KeypointsTemplate = {
  id: "cow",
  vertices: [
    {
      x: 0.5,
      y: 0.1,
      features: {
        label: "museau",
        state: "visible",
      },
    },
    {
      x: 0.5,
      y: 0.5,
      features: {
        label: "dosA",
        state: "visible",
      },
    },
    {
      x: 0.5,
      y: 0.9,
      features: {
        label: "dosD",
        state: "visible",
      },
    },
    {
      x: 0.5,
      y: 0.23,
      features: {
        label: "chignon",
        state: "visible",
      },
    },
    {
      x: 0.5,
      y: 0.37,
      features: {
        label: "cou",
        state: "visible",
      },
    },
    {
      x: 0.5,
      y: 0.63,
      features: {
        label: "dosB",
        state: "visible",
      },
    },
    {
      x: 0.5,
      y: 0.77,
      features: {
        label: "dosC",
        state: "visible",
      },
    },
    {
      x: 0.3,
      y: 0.5,
      features: {
        label: "AG",
        state: "visible",
      },
    },
    {
      x: 0.7,
      y: 0.5,
      features: {
        label: "AD",
        state: "visible",
      },
    },
    {
      x: 0.7,
      y: 0.9,
      features: {
        label: "PD",
        state: "visible",
      },
    },
    {
      x: 0.3,
      y: 0.9,
      features: {
        label: "PG",
        state: "visible",
      },
    },
  ],
  edges: [
    [0, 3],
    [3, 4],
    [4, 1],
    [1, 5],
    [5, 6],
    [6, 2],
    [1, 7],
    [1, 8],
    [2, 9],
    [2, 10],
  ],
};

export const templates: KeypointsTemplate[] = [face, person, cow];
