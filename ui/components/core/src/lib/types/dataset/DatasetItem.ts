/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import { Annotation, annotationSchema } from "./annotations";
import { baseDataFieldsSchema, type BaseDataFields } from "./datasetTypes";
import { Entity, entitySchema } from "./entities";
import { Item, itemSchema } from "./items";
import { View, viewSchema } from "./views";

export const datasetItemSchema = z.object({
  item: baseDataFieldsSchema(itemSchema),
  entities: z.record(z.string(), z.array(baseDataFieldsSchema(entitySchema))),
  annotations: z.record(z.string(), z.array(baseDataFieldsSchema(annotationSchema))),
  views: z.record(
    z.string(),
    baseDataFieldsSchema(viewSchema).or(z.array(baseDataFieldsSchema(viewSchema))),
  ),
});
export type DatasetItemType = z.infer<typeof datasetItemSchema>;

export class DatasetItem implements DatasetItemType {
  item: Item;
  entities: Record<string, Entity[]>;
  annotations: Record<string, Annotation[]>;
  views: Record<string, View | View[]>;

  //UI only fields
  ui: {
    datasetId: string;
    type: string;
  } = { datasetId: "", type: "" };

  constructor(obj: DatasetItemType) {
    datasetItemSchema.parse(obj);
    this.item = new Item(obj.item);

    this.entities = Entity.deepCreateInstanceArray(obj.entities);
    this.annotations = Annotation.deepCreateInstanceArray(obj.annotations);
    this.views = View.deepCreateInstanceArrayOrPlain(
      obj.views as unknown as Record<string, BaseDataFields<View> | BaseDataFields<View>[]>,
    );
  }
}
