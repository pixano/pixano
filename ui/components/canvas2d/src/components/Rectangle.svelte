<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  // Imports
  import Konva from "konva";
  import { Rect, Label, Tag, Text, Group } from "svelte-konva";
  import type { BBox, Shape } from "@pixano/core";

  import { BBOX_STROKEWIDTH } from "../lib/constants";
  import {
    getNewRectangleDimensions,
    onDragMove,
    stickLabelsToRectangle,
    toggleIsEditingBBox,
  } from "../api/rectangleApi";

  export let stage: Konva.Stage;
  export let bbox: BBox;
  export let colorScale: (id: string) => string;
  export let zoomFactor: number;
  export let viewId: string;
  export let newShape: Shape;

  let currentRect: Konva.Rect = stage.findOne(`#rect${bbox.id}`);

  $: {
    toggleIsEditingBBox(bbox.editing ? "on" : "off", stage, bbox.id);
  }

  function updateDimensions(rect: Konva.Rect) {
    const coords = getNewRectangleDimensions(rect, stage, viewId);
    newShape = {
      status: "editing",
      type: "rectangle",
      shapeId: bbox.id,
      coords,
    };
  }

  const resizeStroke = () => {
    currentRect.setAttrs({
      width: currentRect.width() * currentRect.scaleX(),
      height: currentRect.height() * currentRect.scaleY(),
      scaleX: 1,
      scaleY: 1,
    });
    const tooltip: Konva.Label = stage.findOne(`#tooltip${bbox.id}`);
    stickLabelsToRectangle(tooltip, currentRect);
  };

  $: {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    currentRect = viewLayer.findOne(`#rect${bbox.id}`);
    if (currentRect) {
      currentRect.on("dragmove", (e) => onDragMove(e, stage, viewId, currentRect, bbox.id));
      currentRect.on("transform", () => resizeStroke());
      currentRect.on("transformend dragend", () => {
        updateDimensions(currentRect);
      });
    }
  }

  const onDoubleClick = () => {
    newShape = {
      status: "editing",
      shapeId: bbox.id,
      highlighted: "self",
      type: "none",
    };
  };

  const onClick = (target: Konva.Group) => {
    const id = target.id();
    if (id !== bbox.id) {
      newShape = {
        status: "editing",
        shapeId: bbox.id,
        highlighted: "all",
        type: "none",
      };
    }
  };
</script>

<Group on:dblclick={onDoubleClick} on:click={(e) => onClick(e.detail.target)}>
  <Rect
    config={{
      id: `rect${bbox.id}`,
      x: bbox.bbox[0],
      y: bbox.bbox[1],
      width: bbox.bbox[2],
      height: bbox.bbox[3],
      stroke: colorScale(bbox.id),
      strokeWidth: bbox.strokeFactor * (BBOX_STROKEWIDTH / zoomFactor),
      opacity: bbox.opacity,
      visible: bbox.visible,
      draggable: bbox.editing,
    }}
  />
  <Label
    config={{
      id: `tooltip${bbox.id}`,
      x: bbox.bbox[0],
      y: bbox.bbox[1],
      width: 500,
      height: 50,
      offsetY: 12,
      visible: bbox.visible,
      scale: {
        x: 1 / zoomFactor,
        y: 1 / zoomFactor,
      },
      opacity: bbox.opacity,
    }}
  >
    <Tag
      config={{
        fill: colorScale(bbox.id),
        stroke: bbox.tooltip ? colorScale(bbox.id) : "transparent",
      }}
    />
    <Text
      config={{
        id: `text${bbox.id}`,
        x: 0,
        y: 0,
        text: bbox.tooltip,
        fontSize: 12,
        fontStyle: "100",
      }}
    />
  </Label>
</Group>
