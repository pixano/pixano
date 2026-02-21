/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, Mask, type SaveItem } from "$lib/types/dataset";

import { rleToString } from "$lib/utils/maskUtils";

/**
 * Convert save data for backend API.
 * Packs uncompressed mask RLE arrays back to compressed RLE string format.
 */
export function prepareSaveData(items: SaveItem[]): SaveItem[] {
  const backObjs: SaveItem[] = [];
  for (const obj of items) {
    if (
      (obj.change_type === "add" || obj.change_type === "update") &&
      obj.data.table_info.group === "annotations" &&
      obj.data.table_info.base_schema === BaseSchema.Mask &&
      Array.isArray((obj.data as Mask).data.counts)
    ) {
      const original = obj.data as Mask;
      const convertedData = { ...original.data, counts: rleToString(original.data.counts as number[]) };
      backObjs.push({ ...obj, data: { ...original, data: convertedData } as Mask });
    } else {
      backObjs.push({ ...obj });
    }
  }
  return backObjs;
}
