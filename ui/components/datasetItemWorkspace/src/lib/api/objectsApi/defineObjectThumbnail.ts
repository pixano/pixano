/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  BaseSchema,
  WorkspaceType,
  type Annotation,
  type BBox,
  type Image,
  type Mask,
  type ObjectThumbnail,
  type SequenceFrame,
} from "@pixano/core";

import type { MView } from ".";
import { getBoundingBoxFromMaskSVG } from "@pixano/canvas2d/src/api/maskApi";
import type { ItemsMeta } from "../../types/datasetItemWorkspaceTypes";

export const defineObjectThumbnail = (
  metas: ItemsMeta,
  views: MView,
  object: Annotation,
): ObjectThumbnail | null => {
  let coords: number[] | undefined = undefined;
  let frame_index: number | undefined = undefined;

  if (object.is_type(BaseSchema.BBox)) {
    const box = object as BBox;
    coords = box.data.coords;
    frame_index = box.ui.frame_index;
  } else if (object.is_type(BaseSchema.Mask)) {
    const mask = object as Mask;
    if (mask.ui.svg) {
      const bbox = getBoundingBoxFromMaskSVG(mask.ui.svg);
      if (bbox) {
        coords = [bbox.x, bbox.y, bbox.width, bbox.height];
      }
    }
    frame_index = mask.ui.frame_index;
  }

  const view_name = object.data.view_ref.name;
  if (!coords || !view_name) return null;
  //prevent bug: if thumbnail is asked before data are fully loaded, we can have a error on a bad key
  if (!(view_name in views)) return null;

  const view =
    metas.type === WorkspaceType.VIDEO
      ? (views[view_name] as SequenceFrame[])[frame_index!]
      : (views[view_name] as Image);

  if (view && (object.is_type(BaseSchema.Mask) || !(object as BBox).data.is_normalized)) {
    coords = [
      coords[0] / view.data.width,
      coords[1] / view.data.height,
      coords[2] / view.data.width,
      coords[3] / view.data.height,
    ];
  }
  return {
    baseImageDimensions: {
      width: view?.data.width,
      height: view?.data.height,
    },
    coords,
    uri: view?.data.url,
    view: view_name,
  };
};
