/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Annotation, DisplayControl, SaveItem } from "@pixano/core";

export const toggleObjectDisplayControl = (
  object: Annotation,
  displayControlProperty: keyof DisplayControl,
  value: boolean,
): Annotation => {
  object.ui.displayControl = {
    ...(object.ui.displayControl || {}),
    [displayControlProperty]: value,
  };
  return object;
};

export const addOrUpdateSaveItem = (objects: SaveItem[], newObj: SaveItem) => {
  const existing_sames = objects.filter((item) => newObj.object.id === item.object.id);
  //remove other refs to this same object (as the last state is the correct one)
  objects = objects.filter((item) => newObj.object.id !== item.object.id);

  if (
    newObj.change_type === "delete" &&
    existing_sames.some((item) => item.change_type === "add")
  ) {
    //deleting an object created in this "session" (after last save): no need to keep delete
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
