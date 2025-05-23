/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, WorkspaceType, type BBox } from "@pixano/core";

import type { MView } from ".";
import {
  HIGHLIGHTED_BOX_STROKE_FACTOR,
  NOT_ANNOTATION_ITEM_OPACITY,
  PRE_ANNOTATION,
} from "../../constants";
import { defineTooltip } from "./defineTooltip";
import { getTopEntity } from "./getTopEntity";

export const mapObjectToBBox = (bbox: BBox, views: MView): BBox | undefined => {
  if (!bbox) return;
  if (!bbox.is_type(BaseSchema.BBox)) return;
  if (bbox.ui.datasetItemType === WorkspaceType.VIDEO && bbox.ui.displayControl.hidden) return;
  if (bbox.data.source_ref.name === PRE_ANNOTATION && bbox.ui.displayControl.highlighted !== "self")
    return;
  if (!bbox.data.view_ref.name) return;
  let bbox_ui_coords = bbox.data.coords;
  if (bbox.data.format === "xyxy") {
    bbox_ui_coords = [
      bbox_ui_coords[0],
      bbox_ui_coords[1],
      bbox_ui_coords[2] - bbox_ui_coords[0],
      bbox_ui_coords[3] - bbox_ui_coords[1],
    ];
  }
  if (bbox.data.is_normalized) {
    const view = views[bbox.data.view_ref.name];
    const image = Array.isArray(view) ? view[0] : view;
    const imageHeight = image.data.height || 1;
    const imageWidth = image.data.width || 1;
    //TODO: manage correctly format -- here we will change user format if save
    bbox_ui_coords = [
      bbox_ui_coords[0] * imageWidth,
      bbox_ui_coords[1] * imageHeight,
      bbox_ui_coords[2] * imageWidth,
      bbox_ui_coords[3] * imageHeight,
    ];
  }
  const entity = getTopEntity(bbox);
  const tooltip = entity ? defineTooltip(bbox, entity) : "";

  return {
    ...bbox,
    data: {
      ...bbox.data,
      coords: bbox_ui_coords,
      format: "xywh",
    },
    ui: {
      ...bbox.ui,
      tooltip,
      opacity: bbox.ui.displayControl.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
      strokeFactor:
        bbox.ui.displayControl.highlighted === "self" ? HIGHLIGHTED_BOX_STROKE_FACTOR : 1,
    },
  } as BBox;
};
