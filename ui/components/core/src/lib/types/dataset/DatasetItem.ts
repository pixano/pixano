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
import { WorkspaceType } from "./workspaceType";

export const datasetItemSchema = z.object({
  item: baseDataFieldsSchema(itemSchema),
  entities: z.record(
    z.string(),
    baseDataFieldsSchema(entitySchema).or(z.array(baseDataFieldsSchema(entitySchema))),
  ),
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
    type: WorkspaceType;
  } = { datasetId: "", type: WorkspaceType.UNDEFINED };

  constructor(obj: DatasetItemType) {
    datasetItemSchema.parse(obj);
    this.item = new Item(obj.item);

    this.entities = Entity.deepCreateInstanceArrayOrPlain(obj.entities);
    this.annotations = Annotation.deepCreateInstanceArray(obj.annotations);
    this.views = View.deepCreateInstanceArrayOrPlain(
      obj.views as unknown as Record<string, BaseDataFields<View> | BaseDataFields<View>[]>,
    );
  }
}
