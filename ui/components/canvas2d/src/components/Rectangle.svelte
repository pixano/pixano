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
  import { afterUpdate, onDestroy, tick } from "svelte";
  import Konva from "konva";
  import { Rect, Group } from "svelte-konva";
  import type { BBox, SelectionTool, Shape } from "@pixano/core";

  import { BBOX_STROKEWIDTH } from "../lib/constants";
  import {
    getNewRectangleDimensions,
    onDragMove,
    stickLabelsToRectangle,
    toggleIsEditingBBox,
  } from "../api/rectangleApi";
  import LabelTag from "./LabelTag.svelte";

  export let stage: Konva.Stage;
  export let bbox: BBox;
  export let colorScale: (id: string) => string;
  export let zoomFactor: number;
  export let viewId: string;
  export let newShape: Shape;
  export let selectedTool: SelectionTool;

  let currentRect: Konva.Rect = stage.findOne(`#rect${bbox.id}`);

  const updateDimensions = (rect: Konva.Rect) => {
    const coords = getNewRectangleDimensions(rect, stage, viewId);
    newShape = {
      status: "editing",
      type: "rectangle",
      shapeId: bbox.id,
      coords,
    };
  };

  const resizeStroke = () => {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    const correctedRect = currentRect.getClientRect({
      skipTransform: false,
      skipShadow: true,
      skipStroke: true,
      relativeTo: viewLayer,
    });
    currentRect.setAttrs({
      x: correctedRect.x,
      y: correctedRect.y,
      width: correctedRect.width,
      height: correctedRect.height,
      rotation: 0,
      scaleX: 1,
      scaleY: 1,
    });
    const tooltip: Konva.Label = stage.findOne(`#tooltip${bbox.id}`);
    stickLabelsToRectangle(tooltip, currentRect);
  };

  const onDoubleClick = () => {
    newShape = {
      status: "editing",
      shapeId: bbox.id,
      highlighted: "self",
      type: "none",
    };
  };

  const onClick = () => {
    if (bbox.highlighted !== "self") {
      newShape = {
        status: "editing",
        shapeId: bbox.id,
        highlighted: "all",
        type: "none",
      };
    }
  };

  onDestroy(() => {
    const transformer: Konva.Transformer = stage.findOne("#transformer");
    if (transformer) {
      transformer.nodes([]);
    }
  });

  afterUpdate(async () => {
    await tick();
    toggleIsEditingBBox(bbox.editing ? "on" : "off", stage, bbox.id);
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    currentRect = viewLayer.findOne(`#rect${bbox.id}`);
    if (currentRect) {
      currentRect.on("dragmove", (e) => onDragMove(e, stage, viewId, currentRect, bbox.id));
      currentRect.on("transform", () => resizeStroke());
      currentRect.on("transformend dragend", () => {
        updateDimensions(currentRect);
      });
    }
  });
</script>

<Group
  on:dblclick={onDoubleClick}
  on:click={onClick}
  config={{ listening: selectedTool?.type === "PAN" }}
>
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
  <LabelTag
    id={bbox.id}
    x={bbox.bbox[0]}
    y={bbox.bbox[1]}
    visible={bbox.visible}
    {zoomFactor}
    opacity={bbox.opacity}
    tooltip={bbox.tooltip}
    color={colorScale(bbox.id)}
  />
</Group>
