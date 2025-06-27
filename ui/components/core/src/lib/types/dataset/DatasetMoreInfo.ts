/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { tableInfoSchema, type TableInfo } from "./datasetTypes";

const countSchema = z.strictObject({
  count: z.number(),
});

const dataSubFieldSchema = z.strictObject({
  source: z.string(),
  split: z.string(),
});
type dataSubField = z.infer<typeof dataSubFieldSchema>;

const moreInfoSchema = z.object({
  annotations: z.record(z.string(), countSchema),
  entities: z.record(z.string(), countSchema),
  views: z.record(z.string(), countSchema),
  embeddings: z.record(z.string(), countSchema),
});
type moreInfo = z.infer<typeof moreInfoSchema>;

const datasetMoreInfoSchema = z.strictObject({
  id: z.string(),
  data: dataSubFieldSchema,
  info: moreInfoSchema,
  table_info: tableInfoSchema,
});

export type DatasetMoreInfoType = z.infer<typeof datasetMoreInfoSchema>;

export class DatasetMoreInfo implements DatasetMoreInfoType {
  id: string;
  data: dataSubField;
  info: moreInfo;
  table_info: TableInfo;

  constructor(obj: DatasetMoreInfoType) {
    datasetMoreInfoSchema.parse(obj);
    this.id = obj.id;
    this.data = obj.data;
    this.info = obj.info;
    this.table_info = obj.table_info;
  }
}
