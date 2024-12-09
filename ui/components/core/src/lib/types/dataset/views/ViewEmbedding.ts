/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import {
  BaseData,
  ndArrayFloatSchema,
  referenceSchema,
  type BaseDataFields,
} from "../datasetTypes";

const viewEmbeddingSchema = z
  .object({
    item_ref: referenceSchema,
    view_ref: referenceSchema,
    vector: ndArrayFloatSchema,
  })
  .passthrough();
type viewEmbeddingType = z.infer<typeof viewEmbeddingSchema>;

export class ViewEmbedding extends BaseData<viewEmbeddingType> {
  constructor(obj: BaseDataFields<viewEmbeddingType>) {
    viewEmbeddingSchema.parse(obj.data);
    super(obj);
  }
}
