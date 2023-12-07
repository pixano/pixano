import type { ItemObject, BBox, DisplayControl } from "@pixano/core";

export const mapObjectToBBox = (obj: ItemObject) => {
  const imageHeight = 426; // TODO100 imageHeight
  const imageWidth = 640; // TODO100
  const x = obj.bbox.coords[0] * imageWidth;
  const y = obj.bbox.coords[1] * imageHeight;
  const w = obj.bbox.coords[2] * imageWidth;
  const h = obj.bbox.coords[3] * imageHeight;
  const catName =
    "category_name" in obj.features ? (obj.features.category_name.value as string) : null;
  const confidence = obj.bbox.confidence != 0.0 ? " " + obj.bbox.confidence.toFixed(2) : "";
  return {
    id: obj.id,
    viewId: obj.view_id,
    catId: obj.features.category_id.value as number,
    bbox: [x, y, w, h],
    tooltip: catName + confidence,
    opacity: 1.0,
    visible: !obj.bbox.displayControl?.hidden,
    editing: obj.displayControl?.editing,
    locked: obj.displayControl?.locked,
  } as BBox;
};

export const toggleObjectDisplayControl = (
  object: ItemObject,
  displayControlProperty: keyof DisplayControl,
  properties: ("bbox" | "mask")[],
) => {
  if (properties.includes("bbox")) {
    object.bbox.displayControl = {
      ...object.bbox.displayControl,
      [displayControlProperty]: !object.bbox.displayControl?.[displayControlProperty],
    };
  }
  if (properties.includes("mask")) {
    if (object.mask) {
      object.mask.displayControl = {
        ...object.mask.displayControl,
        [displayControlProperty]: !object.displayControl?.[displayControlProperty],
      };
    }
  }
  if (properties.includes("bbox") && properties.includes("mask")) {
    object.displayControl = {
      ...object.displayControl,
      [displayControlProperty]: !object.displayControl?.[displayControlProperty],
    };
  }
  console.log({ object });
  return object;
};
