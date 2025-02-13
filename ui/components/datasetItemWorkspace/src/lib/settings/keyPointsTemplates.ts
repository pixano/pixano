/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { KeypointsTemplate } from "@pixano/core";

const face: KeypointsTemplate = {
  id: "id_face",
  template_id: "face",
  vertices: [
    {
      x: 0.3,
      y: 0.25,
      features: {
        label: "eye left",
        color: "blue",
      },
    },
    {
      x: 0.6,
      y: 0.25,
      features: {
        label: "eye right",
        color: "blue",
      },
    },
    {
      x: 0.45,
      y: 0.45,
      features: {
        label: "nose",
        color: "green",
      },
    },
    {
      x: 0.45,
      y: 0.75,
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
  id: "id_person",
  template_id: "person",
  vertices: [
    {
      x: 0.45,
      y: 0.1,
      features: {
        label: "head",
        state: "visible",
      },
    },
    {
      x: 0.45,
      y: 0.3,
      features: {
        label: "middle",
        state: "visible",
      },
    },
    {
      x: 0.25,
      y: 0.3,
      features: {
        label: "left arm",
        state: "visible",
      },
    },
    {
      x: 0.65,
      y: 0.3,
      features: {
        label: "right arm",
        state: "visible",
      },
    },
    {
      x: 0.45,
      y: 0.5,
      features: {
        label: "belly",
        state: "visible",
      },
    },
    {
      x: 0.25,
      y: 0.8,
      features: {
        label: "left foot",
        state: "visible",
      },
    },
    {
      x: 0.65,
      y: 0.8,
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
  id: "id_cow",
  template_id: "cow",
  vertices: [
    {
      x: 0.45,
      y: 0.1,
      features: {
        label: "museau",
        state: "visible",
      },
    },
    {
      x: 0.45,
      y: 0.4,
      features: {
        label: "dosA",
        state: "visible",
      },
    },
    {
      x: 0.45,
      y: 0.8,
      features: {
        label: "dosD",
        state: "visible",
      },
    },
    {
      x: 0.45,
      y: 0.2,
      features: {
        label: "chignon",
        state: "visible",
      },
    },
    {
      x: 0.45,
      y: 0.3,
      features: {
        label: "cou",
        state: "visible",
      },
    },
    {
      x: 0.45,
      y: 0.53,
      features: {
        label: "dosB",
        state: "visible",
      },
    },
    {
      x: 0.45,
      y: 0.66,
      features: {
        label: "dosC",
        state: "visible",
      },
    },
    {
      x: 0.25,
      y: 0.4,
      features: {
        label: "AG",
        state: "visible",
      },
    },
    {
      x: 0.65,
      y: 0.4,
      features: {
        label: "AD",
        state: "visible",
      },
    },
    {
      x: 0.65,
      y: 0.8,
      features: {
        label: "PD",
        state: "visible",
      },
    },
    {
      x: 0.25,
      y: 0.8,
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
