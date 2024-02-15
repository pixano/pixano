import type { BBox, Mask, SelectionTool } from "@pixano/core";
import LockIcon from "@pixano/core/src/assets/icons/lockIcon.svg";
import Konva from "konva";
import simplify from "simplify-js";

import { BBOX_STROKEWIDTH, MASK_STROKEWIDTH } from "../lib/constants";
import type { PolygonGroupDetails, PolygonGroupPoint } from "../lib/types/canvas2dTypes";

const stickLabelsToRectangle = (tooltip: Konva.Label, lockIcon: Konva.Label, rect: Konva.Rect) => {
  tooltip.x(rect.x());
  tooltip.y(rect.y());
  lockIcon.x(rect.x());
  lockIcon.y(rect.y() + rect.height());
};

export const toggleIsEditingBBox = (
  value: "on" | "off",
  stage: Konva.Stage,
  currentBox: BBox,
  bboxes: BBox[],
) => {
  const rectGroup: Konva.Group = stage.findOne(`#${currentBox.id}`);
  const rect: Konva.Rect = rectGroup.findOne(`#rect${currentBox.id}`);
  if (rect) {
    rectGroup.listening(value === "on");
    const transformer: Konva.Transformer = stage.findOne("#transformer");
    const nodes = transformer.nodes();
    transformer.nodes(
      value === "on" ? [rect] : [...nodes.filter((node) => node.id() !== rect.id())],
    );
    return bboxes.map((bbox) => {
      if (bbox.id === currentBox.id) {
        bbox.editing = value === "on";
      }
      return bbox;
    });
  }
};

export const getNewRectangleDimensions = (rect: Konva.Rect, image: HTMLImageElement) => {
  const width = rect?.width();
  const height = rect?.height();
  const scaleX = rect?.scaleX();
  const scaleY = rect?.scaleY();
  const imageWidth = image.width;
  const imageHeight = image.height;
  const newX = (rect?.x() + (width * scaleX - width) / 2) / imageWidth;
  const newY = (rect?.y() + (height * scaleY - height) / 2) / imageHeight;
  const newWidth = (width * scaleX) / imageWidth;
  const newHeight = (height * scaleY) / imageHeight;
  return [newX, newY, newWidth, newHeight];
};

export const toggleBBoxIsLocked = (stage: Konva.Stage, currentBox: BBox) => {
  const rect: Konva.Rect = stage.findOne(`#rect${currentBox.id}`);
  const lockIcon = stage.findOne(`#lockTooltip${currentBox.id}`);
  lockIcon.opacity(currentBox.locked ? 1 : 0);
  const isLocked = currentBox.locked;
  rect.listening(!isLocked);
  return currentBox;
};

export function addBBox(
  bbox: BBox,
  color: string,
  bboxGroup: Konva.Group,
  image: Konva.Image,
  viewId: string,
  zoomFactor: Record<string, number>,
  updateDimensions: (bbox: Konva.Rect) => void,
) {
  const x = image.x() + bbox.bbox[0];
  const y = image.y() + bbox.bbox[1];
  const rect_width = bbox.bbox[2];
  const rect_height = bbox.bbox[3];

  const bboxKonva = new Konva.Group({
    id: bbox.id,
    visible: bbox.visible,
    opacity: bbox.opacity,
    listening: false,
  });

  const bboxRect = new Konva.Rect({
    id: `rect${bbox.id}`,
    x,
    y,
    width: rect_width,
    height: rect_height,
    stroke: color,
    draggable: true,
    strokeWidth: BBOX_STROKEWIDTH / zoomFactor[viewId],
  });

  bboxKonva.add(bboxRect);

  // Create a tooltip for bounding box category and confidence
  const tooltip = new Konva.Label({
    id: `tooltip${bbox.id}`,
    x,
    y,
    width: 500,
    height: 50,
    offsetY: 12,
    scale: {
      x: 1 / zoomFactor[viewId],
      y: 1 / zoomFactor[viewId],
    },
  });

  // Add a tag
  tooltip.add(
    new Konva.Tag({
      fill: color,
      stroke: bbox.tooltip ? color : "transparent",
    }),
  );

  // Add text
  tooltip.add(
    new Konva.Text({
      id: `text${bbox.id}`,
      x: 24,
      y: 0,
      text: bbox.tooltip,
      fontSize: 12,
      fontStyle: "100",
    }),
  );

  // Create lock icon hidden by default
  const lockTooltip = new Konva.Label({
    id: `lockTooltip${bbox.id}`,
    x,
    y: y + rect_height,
    opacity: 0,
    offsetY: 24,
    width: 24,
    height: 24,
    scale: {
      x: 1 / zoomFactor[viewId],
      y: 1 / zoomFactor[viewId],
    },
  });

  lockTooltip.add(
    new Konva.Tag({
      fill: color,
      stroke: color,
    }),
  );

  const imageObj = new Image();
  imageObj.onload = function () {
    const icon = new Konva.Image({
      x: 0,
      y: 0,
      image: imageObj,
      width: 24,
      height: 24,
      fill: color,
    });

    // add the shape to the layer
    lockTooltip.add(icon);
  };

  imageObj.src = LockIcon;

  // Add to group
  bboxKonva.add(tooltip);
  bboxKonva.add(lockTooltip);
  bboxGroup.add(bboxKonva);

  bboxRect.on("transform", function () {
    const rect: Konva.Rect = bboxKonva.findOne(`#rect${bbox.id}`);
    rect.setAttrs({
      width: rect.width() * rect.scaleX(),
      height: rect.height() * rect.scaleY(),
      scaleX: 1,
      scaleY: 1,
    });
    stickLabelsToRectangle(tooltip, lockTooltip, bboxRect);
  });

  bboxRect.on("dragmove", function (e) {
    const imageSize = image.getSize();
    if (e.target.x() < 0) {
      bboxRect.x(0);
    }
    if (e.target.x() > imageSize.width - bboxRect.width()) {
      bboxRect.x(imageSize.width - bboxRect.width());
    }
    if (e.target.y() < 0) {
      bboxRect.y(0);
    }
    if (e.target.y() > imageSize.height - bboxRect.height()) {
      bboxRect.y(imageSize.height - bboxRect.height());
    }
    stickLabelsToRectangle(tooltip, lockTooltip, bboxRect);
  });

  bboxRect.on("transformend dragend", () => {
    const box: Konva.Rect = bboxKonva.findOne(`#rect${bbox.id}`);
    updateDimensions(box);
  });
}

export function addMask(
  mask: Mask,
  color: string,
  maskGroup: Konva.Group,
  image: Konva.Image,
  viewId: string,
  stage: Konva.Stage,
  zoomFactor: Record<string, number>,
) {
  const x = image.x();
  const y = image.y();
  const scale = image.scale();

  const style = new Option().style;
  style.color = color;

  //utility functions to extract coords from SVG
  //works only with SVG format "Mx0 y0 Lx1 y1 ... xn yn"
  // --> format generated by convertSegmentsToSVG
  function m_part(svg: string) {
    const splits = svg.split(" ");
    const x = splits[0].slice(1); //remove "M"
    return { x: parseInt(x), y: parseInt(splits[1]) };
  }
  function l_part(svg: string) {
    const splits = svg.split(" ");
    const x0 = splits[2].slice(1); //remove "L"
    const res = [{ x: parseInt(x0), y: parseInt(splits[3]) }];
    for (let i = 4; i < splits.length; i += 2) {
      res.push({
        x: parseInt(splits[i]),
        y: parseInt(splits[i + 1]),
      });
    }
    return res;
  }
  const maskKonva = new Konva.Shape({
    id: mask.id,
    x: x,
    y: y,
    width: stage.width(),
    height: stage.height(),
    fill: `rgba(${style.color.replace("rgb(", "").replace(")", "")}, 0.35)`,
    stroke: style.color,
    strokeWidth: MASK_STROKEWIDTH / zoomFactor[viewId],
    scale,
    visible: mask.visible,
    opacity: mask.opacity,
    listening: false,
    sceneFunc: (ctx, shape) => {
      ctx.beginPath();
      for (let i = 0; i < mask.svg.length; ++i) {
        const start = m_part(mask.svg[i]);
        ctx.moveTo(start.x, start.y);
        const l_pts = l_part(mask.svg[i]);
        for (const pt of l_pts) {
          ctx.lineTo(pt.x, pt.y);
        }
      }
      ctx.fillStrokeShape(shape);
    },
  });

  maskGroup.add(maskKonva);
}

export function destroyDeletedObjects(objectsIds: Array<string>, objectsGroup: Konva.Group) {
  // Check if Object ID still exist in list. If not, object is deleted and must be removed from group
  const objectsToDestroy: Konva.Group[] = []; // need to build a list to not destroy while looping children
  for (const obj of objectsGroup.children) {
    if (!objectsIds.includes(obj.id())) objectsToDestroy.push(obj as Konva.Group);
  }
  for (const obj of objectsToDestroy) obj.destroy();
}

export function findOrCreateCurrentMask(viewId: string, stage: Konva.Stage): Konva.Group {
  const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);

  const currentAnnGroup: Konva.Group = viewLayer.findOne("#currentAnnotation");

  // Get and update the current annotation masks
  let currentMaskGroup: Konva.Group = currentAnnGroup.findOne("#currentMask");

  if (!currentMaskGroup) {
    currentMaskGroup = new Konva.Group({
      id: "currentMask",
    });
    currentAnnGroup.add(currentMaskGroup);
  }
  return currentMaskGroup;
}

export function clearCurrentAnn(viewId: string, stage: Konva.Stage, selectedTool: SelectionTool) {
  const viewLayer: Konva.Layer = stage?.findOne(`#${viewId}`);
  if (viewLayer) {
    const currentAnnGroup: Konva.Group = viewLayer.findOne("#currentAnnotation");
    const currentMaskGroup: Konva.Group = currentAnnGroup.findOne("#currentMask");
    if (currentMaskGroup) currentMaskGroup.destroy();
    if (selectedTool?.postProcessor) selectedTool.postProcessor.reset();
  }
}

export function mapMaskPointsToLineCoordinates(masks: Mask[]): PolygonGroupDetails[] {
  const mappedMasks: PolygonGroupDetails[] = masks
    ?.filter((mask) => mask)
    .map((mask) => {
      const points = mask.coordinates || mask.rle.counts;
      return {
        visible: mask.visible,
        editing: mask.editing,
        id: mask.id,
        status: mask?.id ? "created" : "creating",
        svg: mask?.svg,
        opacity: mask.opacity || 1,
        viewId: mask.viewId,
        points: points.reduce((acc, val, i) => {
          if (i % 2 === 0) {
            acc.push({
              x: val,
              y: points[i + 1],
              id: i / 2,
            });
          }
          return acc;
        }, [] as PolygonGroupPoint[]),
      };
    })
    .map((mask) => {
      // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment, @typescript-eslint/no-unsafe-call
      const simplifiedPoints = simplify(mask.points, 4, false);
      mask.points = simplifiedPoints as PolygonGroupPoint[];
      return mask as PolygonGroupDetails;
    });

  return mappedMasks;
}
