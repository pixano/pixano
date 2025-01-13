/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import type { BaseDataFields } from "../datasetTypes";
import { Entity, type EntityType, type EntityUIFields } from "./Entity";

const trackSchema = z
  .object({
    name: z.string(),
  })
  .passthrough();

export type TrackType = z.infer<typeof trackSchema>; //export if needed

export class Track extends Entity {
  ui: EntityUIFields & {
    hidden?: boolean;
  } = { hidden: false };

  constructor(obj: BaseDataFields<TrackType>) {
    trackSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<EntityType>);
  }

  static nonFeaturesFields(): string[] {
    //return super.nonFeaturesFields().concat(["name"]);
    return super.nonFeaturesFields(); //name is a feature indeed !
  }
}
