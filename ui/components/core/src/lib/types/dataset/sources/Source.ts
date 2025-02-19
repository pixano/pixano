/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { BaseData, type BaseDataFields } from "../datasetTypes";

const sourceSchema = z
  .object({
    name: z.string(),
    kind: z.string(),
    metadata: z.record(z.string(), z.any()),
  })
  .strict();
export type sourceType = z.infer<typeof sourceSchema>;

export class Source extends BaseData<sourceType> {
  constructor(obj: BaseDataFields<sourceType>) {
    sourceSchema.parse(obj.data);
    super(obj);
  }
}
