/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { WorkspaceType, type Keypoints, type KeypointsTemplate } from "@pixano/core";

import type { MView } from ".";
import { templates } from "../../settings/keyPointsTemplates";

export const mapObjectToKeypoints = (
  keypoints: Keypoints,
  views: MView,
): KeypointsTemplate | undefined => {
  if (
    !keypoints ||
    !keypoints.data.view_ref.name ||
    (keypoints.ui.datasetItemType === WorkspaceType.VIDEO && keypoints.ui.displayControl.hidden)
  )
    return;
  const template = templates.find((t) => t.template_id === keypoints.data.template_id);
  if (!template) return;

  const view = views[keypoints.data.view_ref.name];
  const image = Array.isArray(view) ? view[0] : view;
  const imageHeight = image.data.height || 1;
  const imageWidth = image.data.width || 1;
  const vertices = [];
  for (let i = 0; i < keypoints.data.coords.length / 2; i++) {
    const x = keypoints.data.coords[i * 2] * imageWidth;
    const y = keypoints.data.coords[i * 2 + 1] * imageHeight;
    const features = {
      ...(template.vertices[i].features || {}),
      ...{ state: keypoints.data.states[i] },
    };
    vertices.push({ x, y, features });
  }
  const kptTemplate = {
    id: keypoints.id,
    template_id: keypoints.data.template_id,
    viewRef: keypoints.data.view_ref,
    entityRef: keypoints.data.entity_ref,
    vertices,
    edges: template.edges,
    ui: keypoints.ui,
    table_info: keypoints.table_info,
  } as KeypointsTemplate;
  if ("frame_index" in keypoints.ui) kptTemplate.ui!.frame_index = keypoints.ui.frame_index;
  if ("top_entities" in keypoints.ui) kptTemplate.ui!.top_entities = keypoints.ui.top_entities;
  return kptTemplate;
};
