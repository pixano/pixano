/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { KeypointAnnotation } from "$lib/types/shapeTypes";

const face: KeypointAnnotation = {
  id: "id_face",
  template_id: "face",
  graph: {
    vertices: [
      { x: 0.3, y: 0.25 },
      { x: 0.6, y: 0.25 },
      { x: 0.45, y: 0.45 },
      { x: 0.45, y: 0.75 },
    ],
    edges: [
      [0, 2],
      [1, 2],
      [2, 3],
    ],
  },
  vertexMetadata: [
    { state: "visible", label: "eye left", color: "blue" },
    { state: "visible", label: "eye right", color: "blue" },
    { state: "visible", label: "nose", color: "green" },
    { state: "visible", label: "mouth", color: "red" },
  ],
};

const person: KeypointAnnotation = {
  id: "id_person",
  template_id: "person",
  graph: {
    vertices: [
      { x: 0.45, y: 0.1 },
      { x: 0.45, y: 0.3 },
      { x: 0.25, y: 0.3 },
      { x: 0.65, y: 0.3 },
      { x: 0.45, y: 0.5 },
      { x: 0.25, y: 0.8 },
      { x: 0.65, y: 0.8 },
    ],
    edges: [
      [0, 1],
      [1, 2],
      [1, 3],
      [1, 4],
      [4, 5],
      [4, 6],
    ],
  },
  vertexMetadata: [
    { state: "visible", label: "head", color: "" },
    { state: "visible", label: "middle", color: "" },
    { state: "visible", label: "left arm", color: "" },
    { state: "visible", label: "right arm", color: "" },
    { state: "visible", label: "belly", color: "" },
    { state: "visible", label: "left foot", color: "" },
    { state: "visible", label: "right foot", color: "" },
  ],
};

const cow: KeypointAnnotation = {
  id: "id_cow",
  template_id: "cow",
  graph: {
    vertices: [
      { x: 0.45, y: 0.1 },
      { x: 0.45, y: 0.4 },
      { x: 0.45, y: 0.8 },
      { x: 0.45, y: 0.2 },
      { x: 0.45, y: 0.3 },
      { x: 0.45, y: 0.53 },
      { x: 0.45, y: 0.66 },
      { x: 0.25, y: 0.4 },
      { x: 0.65, y: 0.4 },
      { x: 0.65, y: 0.8 },
      { x: 0.25, y: 0.8 },
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
  },
  vertexMetadata: [
    { state: "visible", label: "museau", color: "" },
    { state: "visible", label: "dosA", color: "" },
    { state: "visible", label: "dosD", color: "" },
    { state: "visible", label: "chignon", color: "" },
    { state: "visible", label: "cou", color: "" },
    { state: "visible", label: "dosB", color: "" },
    { state: "visible", label: "dosC", color: "" },
    { state: "visible", label: "AG", color: "" },
    { state: "visible", label: "AD", color: "" },
    { state: "visible", label: "PD", color: "" },
    { state: "visible", label: "PG", color: "" },
  ],
};

export const templates: KeypointAnnotation[] = [face, person, cow];
