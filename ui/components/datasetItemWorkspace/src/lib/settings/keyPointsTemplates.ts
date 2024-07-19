/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

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

const vdp_parts_vehicle: KeypointsTemplate = {
  id: "vdp_parts_vehicle",
  vertices: Array.from({ length: 36 }, (_, i) => ({
    x: 0.5,
    y: 0.5,
    features: {
      label: `${i}`,
      state: "visible",
    },
  })),
  edges: [
    [0, 1],
    [1, 2],
    [2, 3],
    [3, 4],
    [4, 5],
    [5, 6],
    [6, 7],
    [7, 8],
    [8, 9],
    [9, 10],
    [10, 11],
    [11, 12],
    [12, 13],
    [13, 14],
    [14, 15],
    [1, 19],
    [2, 20],
    [3, 21],
    [4, 22],
    [5, 23],
    [6, 24],
    [7, 25],
    [0, 15],
    [0, 18],
    [18, 19],
    [19, 20],
    [20, 21],
    [21, 22],
    [22, 23],
    [23, 24],
    [24, 25],
    [25, 26],
    [26, 27],
    [27, 28],
    [28, 29],
    [29, 30],
    [30, 31],
    [31, 32],
    [32, 33],
    [33, 18],
  ],
};

const vdp_parts_person: KeypointsTemplate = {
  id: "vdp_parts_person",
  vertices: Array.from({ length: 8 }, (_, i) => ({
    x: 0.5,
    y: 0.5,
    features: {
      label: `${i}`,
      state: "visible",
    },
  })),
  edges: [[0, 1], [1, 2], [2, 3], [3, 0], [0, 4], [4, 5], [5, 6], [6, 7], [7, 4], [5, 1], [2, 6], [7, 3]],
};

const vdp_kpt13pts: KeypointsTemplate = {
  id: "vdp_kpt13pts",
  vertices: Array.from({ length: 13 }, (_, i) => ({
    x: 0.5,
    y: 0.5,
    features: {
      label: `${i}`,
      state: "visible",
    },
  })),
  edges: [[0, 1], [1, 2], [1, 3], [2, 4], [3, 5], [4, 6], [1, 7], [2, 8], [7, 9], [7, 8], [8, 10], [9, 11], [10, 12]],
};

const vdp_kpt17pts: KeypointsTemplate = {
  id: "vdp_kpt17pts",
  vertices: Array.from({ length: 17 }, (_, i) => ({
    x: 0.5,
    y: 0.5,
    features: {
      label: `${i}`,
      state: "visible",
    },
  })),
  edges: [[0, 1], [0, 2], [0, 3], [3, 4], [3, 5], [4, 6], [5, 7], [6, 8], [3, 9], [4, 10], [9, 11], [9, 10], [10, 12], [11, 13], [12, 14], [13, 15], [14, 16]],
};

export const templates: KeypointsTemplate[] = [face, person, cow, vdp_parts_vehicle, vdp_parts_person, vdp_kpt13pts, vdp_kpt17pts];
