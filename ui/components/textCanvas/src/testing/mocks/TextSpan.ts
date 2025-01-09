/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, TextSpan, type TableInfo, type TextSpanType } from "@pixano/core";
import { mockAnnotationType } from "./shared";

const mockTableInfo: TableInfo = {
  base_schema: BaseSchema.TextSpan,
  group: "annotations",
  name: "text_spans",
};

const mockBaseField = {
  table_info: mockTableInfo,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

export const createMockTextSpan = (props: { id: string; data: TextSpanType }) =>
  new TextSpan({
    ...mockBaseField,
    id: props.id,
    data: { ...props.data, ...mockAnnotationType },
  });
