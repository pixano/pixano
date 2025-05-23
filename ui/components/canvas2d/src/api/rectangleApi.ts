/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import type { KonvaEventObject } from "konva/lib/Node";

import { BBox, type Reference } from "@pixano/core";

export const toggleIsEditingBBox = (
  value: "on" | "off",
  stage: Konva.Stage,
  bboxId: BBox["id"],
) => {
  const rect: Konva.Rect = stage.findOne(`#rect${bboxId}`);
  const transformer: Konva.Transformer = stage.findOne("#transformer");
  if (rect && transformer) {
    transformer.moveToTop();
    const nodes = transformer.nodes();
    transformer.nodes(
      value === "on" ? [rect] : [...nodes.filter((node) => node.id() !== rect.id())],
    );
  } else {
    transformer?.nodes([]);
  }
};

export const onDragMove = (
  e: KonvaEventObject<"dragmove">,
  stage: Konva.Stage,
  viewRef: Reference,
  currentRect: Konva.Rect,
  bboxId: string,
) => {
  const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);
  const image = viewLayer.findOne(`#image-${viewRef.name}`);
  if (!image) {
    return;
  }
  const imageSize = image.getSize();
  if (e.target.x() < 0) {
    currentRect.x(0);
  }
  if (e.target.x() > imageSize.width - currentRect.width()) {
    currentRect.x(imageSize.width - currentRect.width());
  }
  if (e.target.y() < 0) {
    currentRect.y(0);
  }
  if (e.target.y() > imageSize.height - currentRect.height()) {
    currentRect.y(imageSize.height - currentRect.height());
  }

  const tooltip: Konva.Label = stage.findOne(`#tooltip${bboxId}`);
  stickLabelsToRectangle(tooltip, currentRect);
};

export const getNewRectangleDimensions = (
  rect: Konva.Rect,
  stage: Konva.Stage,
  viewRef: Reference,
) => {
  const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);
  const image = viewLayer.findOne(`#image-${viewRef.name}`);
  const imageSize = image.getSize();
  const width = rect?.width();
  const height = rect?.height();
  const imageWidth = imageSize.width;
  const imageHeight = imageSize.height;
  const newX = rect?.x() / imageWidth;
  const newY = rect?.y() / imageHeight;
  const newWidth = width / imageWidth;
  const newHeight = height / imageHeight;
  return [newX, newY, newWidth, newHeight];
};

export const resizeStroke = (rect: Konva.Rect) => {
  rect.setAttrs({
    width: rect.width() * rect.scaleX(),
    height: rect.height() * rect.scaleY(),
    scaleX: 1,
    scaleY: 1,
  });
};

export const stickLabelsToRectangle = (tooltip: Konva.Label, rect: Konva.Rect) => {
  tooltip.x(rect.x());
  tooltip.y(rect.y());
};
