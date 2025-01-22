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
  type SequenceFrame,
} from "@pixano/core";
import type { MView } from ".";
import type { ItemsMeta } from "../../types/datasetItemWorkspaceTypes";

export const defineObjectThumbnail = (metas: ItemsMeta, views: MView, object: Annotation) => {
  let box: BBox | undefined = undefined;
  if (object.is_type(BaseSchema.BBox)) {
    box = object as BBox;
  }
  const view_name = object.data.view_ref.name;
  if (!box || !box.is_type(BaseSchema.BBox) || !view_name) return null;
  //prevent bug: if thumbnail is asked before data are fully loaded, we can have a error on a bad key
  if (!(view_name in views)) return null;

  const view =
    metas.type === WorkspaceType.VIDEO
      ? (views[view_name] as SequenceFrame[])[box.ui.frame_index!]
      : (views[view_name] as Image);
  let coords = box.data.coords;
  if (view && !box.data.is_normalized) {
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
  };
};
