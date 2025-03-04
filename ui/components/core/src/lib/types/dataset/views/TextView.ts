/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { BaseSchema } from "../BaseSchema";
import type { BaseDataFields } from "../datasetTypes";
import { View, type ViewType } from "./View";

export const textSchema = z.object({
  content: z.string(),
});

export type TextViewType = z.infer<typeof textSchema>; //export if needed

export class TextView extends View {
  declare data: TextViewType & ViewType;

  constructor(obj: BaseDataFields<TextViewType>) {
    textSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<ViewType>);
    this.data = obj.data as TextViewType & ViewType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["content"]);
  }
}

export const isTextView = (view: View | View[]): view is TextView =>
  Array.isArray(view) === false && view.table_info.base_schema === BaseSchema.TextView;
