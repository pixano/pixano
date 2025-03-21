/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { WorkspaceType } from "./workspaceType";

function z_enumFromArray(array: string[]) {
  return z.enum([array[0], ...array.slice(1)]);
}

const datasetInfoSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    description: z.string(),
    size: z.string(),
    preview: z.string(),
    workspace: z_enumFromArray(Object.values(WorkspaceType)),
    num_items: z.number(),
    isFiltered: z.optional(z.boolean()),
  })
  .strict();
export type DatasetInfoType = z.infer<typeof datasetInfoSchema>;

export class DatasetInfo implements DatasetInfoType {
  id: string;
  name: string;
  description: string;
  num_items: number;
  size: string;
  preview: string;
  workspace: WorkspaceType;
  isFiltered?: boolean;

  constructor(obj: DatasetInfoType) {
    datasetInfoSchema.parse(obj);
    this.id = obj.id;
    this.name = obj.name;
    this.description = obj.description;
    this.num_items = obj.num_items;
    this.size = obj.size;
    this.preview = obj.preview;
    this.workspace = obj.workspace as WorkspaceType;
    this.isFiltered = obj.isFiltered;
  }
}
