/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { BaseSchema } from "../BaseSchema";
import { initDisplayControl, type BaseDataFields } from "../datasetTypes";
import { WorkspaceType } from "../workspaceType";
import { Annotation, type AnnotationType, type AnnotationUIFields } from "./Annotation";

const trackletSchema = z
  .object({
    start_timestep: z.number(),
    end_timestep: z.number(),
    start_timestamp: z.number(),
    end_timestamp: z.number(),
  })
  .passthrough();

export type TrackletType = z.infer<typeof trackletSchema>;
export class Tracklet extends Annotation {
  declare data: TrackletType & AnnotationType;

  //UI only fields
  ui: AnnotationUIFields & {
    childs: Annotation[];
  } = { datasetItemType: WorkspaceType.VIDEO, childs: [], displayControl: initDisplayControl };

  constructor(obj: BaseDataFields<TrackletType>) {
    if (obj.table_info.base_schema !== BaseSchema.Tracklet) throw new Error("Not a Tracklet");
    trackletSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as TrackletType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super
      .nonFeaturesFields()
      .concat(["start_timestep", "end_timestep", "start_timestamp", "end_timestamp"]);
  }
}
