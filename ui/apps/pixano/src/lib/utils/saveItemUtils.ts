/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, Mask, type SaveItem, type Schema } from "$lib/types/dataset";
import { saveData } from "$lib/stores/workspaceStores.svelte";
import { rleToString } from "$lib/utils/maskUtils";

export const addOrUpdateSaveItem = (objects: SaveItem[], newObj: SaveItem) => {
  const existing_sames = objects.filter(
    (item) =>
      newObj.data.id === item.data.id &&
      Object.keys(newObj.data.table_info).every(
        (key) =>
          newObj.data.table_info[key as keyof typeof newObj.data.table_info] ===
          item.data.table_info[key as keyof typeof item.data.table_info],
      ),
  );
  //remove other refs to this same object (as the last state is the correct one)
  objects = objects.filter((item) => !existing_sames.includes(item));

  if (
    newObj.change_type === "delete" &&
    existing_sames.some((item) => item.change_type === "add")
  ) {
    //deleting an object created in this "session" (after last save): no need to keep delete
    //if Source - pixano_source is the only object in objects, discard it too (it will be put back if needed)
    if (
      objects.length === 1 &&
      objects[0].change_type === "add" &&
      objects[0].data.table_info.base_schema === BaseSchema.Source &&
      objects[0].data.id === "pixano_source"
    ) {
      return [];
    }
    return objects;
  }
  if (
    newObj.change_type === "update" &&
    existing_sames.some((item) => item.change_type === "add")
  ) {
    newObj.change_type = "add";
  }
  objects.push(newObj);
  return objects;
};

/**
 * Shorthand for the common saveData.update(sd => addOrUpdateSaveItem(sd, { change_type, data })) pattern.
 */
export function saveTo(changeType: SaveItem["change_type"], data: Schema): void {
  saveData.update((sd) => addOrUpdateSaveItem(sd, { change_type: changeType, data }));
}

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
