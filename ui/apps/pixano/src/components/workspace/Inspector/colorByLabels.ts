/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ColorByAttribute } from "$lib/coloring/colorByCatalogue";
import { ANNOTATION_TYPE_META } from "$lib/constants/annotationTypeMeta";
import { humanizeTableName } from "$lib/utils/labels";

/** The heading an attribute is listed under in the "Color by" menu. */
export function colorByGroupHeading(attribute: ColorByAttribute): string {
  if (attribute.scope === "entity") return "Entity attributes";
  return ANNOTATION_TYPE_META[attribute.baseSchema]?.label ?? humanizeTableName(attribute.table);
}

/** An attribute's name outside its menu group: "Category", "Bounding box › Confidence". */
export function colorByOptionLabel(attribute: ColorByAttribute): string {
  return attribute.scope === "entity"
    ? attribute.label
    : `${colorByGroupHeading(attribute)} › ${attribute.label}`;
}
