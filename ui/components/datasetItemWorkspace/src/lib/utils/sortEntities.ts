/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, Entity, Tracklet } from "@pixano/core";

const getFirstFrame = (track: Entity): number => {
  return track.ui.childs && track.ui.childs.length > 0
    ? Math.min(
        ...track.ui.childs
          .filter((ann) => ann.is_type(BaseSchema.Tracklet))
          .map((tracklet) => (tracklet as Tracklet).data.start_timestep),
      )
    : Infinity;
};
export const sortEntities = (a: Entity, b: Entity): number => {
  let result = 0;
  if (a.is_type(BaseSchema.Track) && b.is_type(BaseSchema.Track)) {
    result = getFirstFrame(a) - getFirstFrame(b);
  }
  if (result === 0 && "name" in a.data && "name" in b.data) {
    result = (a.data["name"] as string).localeCompare(b.data["name"] as string);
  }
  if (result === 0) {
    result = a.id.localeCompare(b.id);
  }
  return result;
};
