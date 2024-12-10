/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Annotation, BBox, Image, SequenceFrame } from "@pixano/core";
import type { MView } from ".";
import type { ItemsMeta } from "../../types/datasetItemWorkspaceTypes";

export const defineObjectThumbnail = (metas: ItemsMeta, views: MView, object: Annotation) => {
  let box: BBox | undefined = undefined;
  if (object.is_bbox) {
    box = object as BBox;
  }
  const view_name = object.data.view_ref.name;
  if (!box || !box.is_bbox || !view_name) return null;
  //prevent bug: if thumbnail is asked before data are fully loaded, we can have a error on a bad key
  if (!(view_name in views)) return null;
  const view =
    metas.type === "video"
      ? (views[view_name] as SequenceFrame[])[box.ui.frame_index!]
      : (views[view_name] as Image);
  const coords = box.data.coords;
  return {
    baseImageDimensions: {
      width: view?.data.width,
      height: view?.data.height,
    },
    coords,
    uri: view?.data.url,
  };
};
