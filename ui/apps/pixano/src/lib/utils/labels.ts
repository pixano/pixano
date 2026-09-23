/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ShapeType } from "$lib/types/shapeTypes";

/**
 * User-facing vocabulary helpers.
 *
 * Internal identifiers (schema/table/field names, shape-type tokens) must never leak
 * into the UI verbatim — these helpers produce the human labels.
 */

const SHAPE_TYPE_LABELS: Record<string, string> = {
  [ShapeType.bbox]: "bounding box",
  [ShapeType.keypoints]: "keypoints",
  [ShapeType.mask]: "mask",
  [ShapeType.polygon]: "polygon",
  [ShapeType.polyline]: "polyline",
  [ShapeType.track]: "track",
  [ShapeType.textSpan]: "text span",
};

/** Human name for a shape type: `bbox` → "bounding box", `textSpan` → "text span". */
export function humanizeShapeType(type: string): string {
  return SHAPE_TYPE_LABELS[type] ?? type.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
}

/**
 * Human label for a schema field name: `category_name` → "Category name",
 * `numInstances` → "Num instances".
 */
export function humanizeFieldName(name: string): string {
  const spaced = name
    .replaceAll("_", " ")
    .replace(/([a-z\d])([A-Z])/g, "$1 $2")
    .trim()
    .toLowerCase();
  return spaced ? spaced[0].toUpperCase() + spaced.slice(1) : name;
}

/** Human label for a schema table name, used as a field-group header. */
export function humanizeTableName(name: string): string {
  return humanizeFieldName(name);
}
