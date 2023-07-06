/**
@copyright CEA-LIST/DIASI/SIALV/LVA (2023)
@author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
@license CECILL-C

This software is a collaborative computer program whose purpose is to
generate and explore labeled data for computer vision applications.
This software is governed by the CeCILL-C license under French law and
abiding by the rules of distribution of free software. You can use, 
modify and/ or redistribute the software under the terms of the CeCILL-C
license as circulated by CEA, CNRS and INRIA at the following URL

http://www.cecill.info
*/

// Imports
import Konva from "konva";

// Used to represent a mask
type Mask = Array<Array<number>>;

// Used to represent a bounding box
interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

// Used to represent some dimensions
interface Dimensions {
  width: number;
  height: number;
}

// Used to represent an offset
interface Offset {
  x: number;
  y: number;
}

/**
 * Transforms a normalized bbox into one with actual coordinates and size
 * @param bbox the normalized bbox
 * @param dims the actual dims of the image
 * @param offset the offset of the bbox
 * @returns the bbox with actual coordinates and size
 */
export function calculateBBoxCoordinates(
  bbox: BoundingBox,
  dims: Dimensions,
  offset: Offset
): BoundingBox {
  return {
    x: bbox.x * dims.width + offset.x,
    y: bbox.y * dims.height + offset.y,
    width: bbox.width * dims.width,
    height: bbox.height * dims.height,
  };
}

/**
 * Transforms a normalized mask into one with actual coordinates and size
 * @param bbox the normalized mask
 * @param dims the actual dims of the image
 * @param offset the offset of the mask
 * @returns the mask with actual coordinates
 */
export function calculateMaskCoordinates(
  mask: Mask,
  dims: Dimensions,
  offset: Offset
): Mask {
  // scale and align point
  const scaleAndAlign = (value: number, index: number) => {
    if (index % 2 == 0) return value * dims.width + offset.x; // value is x
    else return value * dims.height + offset.y; // value is y
  };

  // For each polygon
  for (let i = 0; i < mask.length; ++i) {
    let polygon: Array<number> = mask[i];

    // For each point
    for (let j = 0; j < polygon.length; ++j)
      polygon[j] = scaleAndAlign(polygon[j], j); // Calculate coordinates
  }

  return mask;
}

/**
 * Clears a stage's layers.
 * @param stage stage to destroy
 */
export function clearCanvas(stage: Konva.Stage) {
  // Clear canvas
  stage.clear();

  // Destroy all children of every layer
  stage.children.forEach((layer) => layer.destroyChildren());
}

/**
 * Draws a tooltip on a group.
 * @param id id of the tooltip
 * @param group group to draw in
 * @param tooltip text to display
 * @param offset coordinates where the tooltip should be drawn
 * @param color background color of the tooltip
 * @param visibility visibility status of the tooltip
 */
export function drawTooltip(
  id: string,
  group: Konva.Group,
  tooltip: string,
  offset: Offset,
  color: string = "black",
  visibility: boolean = true
) {
  // Create a label object
  const label = new Konva.Label({
    id: id,
    x: offset.x,
    y: offset.y,
    visible: visibility,
  });

  // Add a tag to the label
  label.add(
    new Konva.Tag({
      fill: color,
      stroke: color,
    })
  );

  // Add some text to the label
  label.add(
    new Konva.Text({
      text: tooltip,
      fontSize: 10,
      fontStyle: "bold",
      padding: 2,
      x: offset.x,
      y: offset.y,
    })
  );

  // Add the label to the group
  group.add(label);
}

/**
 * Adds a bounding box to a group
 * @param id id of the box
 * @param group group to draw in
 * @param bbox box to draw
 * @param color color of the outline
 * @param dashed box style
 * @param visibility box visibility status
 */
export function drawBoundingBox(
  id: string = "",
  group: Konva.Group,
  bbox: BoundingBox,
  color: string = "black",
  dashed: boolean = false,
  visibility: boolean = true
) {
  const k_bbox = new Konva.Rect({
    x: bbox.x,
    y: bbox.y,
    id: id,
    width: bbox.width,
    height: bbox.height,
    stroke: color,
    strokeWidth: 3,
    visible: visibility,
    dash: dashed ? [10, 10] : [],
  });

  group.add(k_bbox);
}

/**
 * Adds a mask to a group
 * @param id id of the mask
 * @param group group to draw in
 * @param mask mask to draw
 * @param color color of the mask
 * @param visibility mask visibility status
 * @param opacity mask opacity
 */
export function drawMask(
  id: string = "",
  group: Konva.Group,
  mask: Mask,
  color: string = "black",
  visibility: boolean = true,
  opacity: number = 0.5
) {
  // Create a group
  let k_mask = new Konva.Group({
    id: id,
    opacity: opacity,
    visible: visibility,
  });

  // For each polygon
  mask.forEach((polygon: Array<number>) => {
    // Create the mask and add it to its group
    const part = new Konva.Line({
      points: polygon,
      fill: color,
      closed: true,
    });

    k_mask.add(part);
  });

  group.add(k_mask);
}

/**
 * Adds an image to a group
 * @param group group to draw in
 * @param image image to draw
 * @param offset offset of the image
 * @param scale scale of the image
 */
export function drawImage(
  group: Konva.Group,
  image: HTMLImageElement,
  offset: Offset,
  scale: number
) {
  const img = new Konva.Image({
    image: image,
    x: offset.x,
    y: offset.y,
    scaleX: scale,
    scaleY: scale,
  });

  group.add(img);
}

/**
 * Adds a label to a layer
 * @param layer layer to label
 * @param label label to write
 * @param offset offset of the label
 */
export function drawLabel(layer: Konva.Layer, label: string, offset: Offset) {
  // Create a label
  const k_label = new Konva.Label({
    x: offset.x + 5,
    y: offset.y + 5,
  });

  // Add a tag to the label
  k_label.add(
    new Konva.Tag({
      fill: "black",
      cornerRadius: 5,
    })
  );

  // Add some text to the label
  k_label.add(
    new Konva.Text({
      text: label,
      fontSize: 15,
      fontStyle: "bold",
      padding: 5,
      fill: "white",
    })
  );

  // Add the label to the layer
  layer.add(k_label);
}

/**
 * Change every mask opacity to match the wanted value.
 * @param group the mask group
 * @param opacity the new opacity
 */
export function updateMasksOpacity(group, opacity: number) {
  group?.children.forEach((mask) => mask.opacity(opacity));
}

/**
 * Zooms in or out of a stage
 * @param stage stage to zoom in/out
 * @param layer layer to zoom in/out
 * @param direction zoom in or zoom out
 */
export function zoom(stage: Konva.Stage, direction) {
  // Defines zoom speed
  const zoomScale = 1.05;

  // Get old scaling
  const oldScale = stage.scaleX();

  // Get mouse position
  const pointer = stage.getPointerPosition();
  const mousePointTo = {
    x: (pointer.x - stage.x()) / oldScale,
    y: (pointer.y - stage.y()) / oldScale,
  };

  // Calculate new scaling
  const newScale = direction > 0 ? oldScale * zoomScale : oldScale / zoomScale;

  // Calculate new position
  const newPos = {
    x: pointer.x - mousePointTo.x * newScale,
    y: pointer.y - mousePointTo.y * newScale,
  };

  // Change scaling and position
  stage.scale({ x: newScale, y: newScale });
  stage.position(newPos);
}
