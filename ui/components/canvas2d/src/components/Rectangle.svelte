<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy, tick } from "svelte";
  import Konva from "konva";
  import { Rect, Group } from "svelte-konva";
  import {
    Annotation,
    SaveShapeType,
    type BBox,
    type SelectionTool,
    type Shape,
  } from "@pixano/core";

  import { BBOX_STROKEWIDTH } from "../lib/constants";
  import {
    getNewRectangleDimensions,
    onDragMove,
    stickLabelsToRectangle,
    toggleIsEditingBBox,
  } from "../api/rectangleApi";
  import LabelTag from "./LabelTag.svelte";
  import { ToolType } from "../tools";

  export let stage: Konva.Stage;
  export let bbox: BBox;
  export let colorScale: (id: string) => string;
  export let zoomFactor: number;
  export let newShape: Shape;
  export let selectedTool: SelectionTool;
  export let merge: (ann: Annotation) => void;

  const updateDimensions = (rect: Konva.Rect) => {
    const coords = getNewRectangleDimensions(rect, stage, bbox.data.view_ref);
    newShape = {
      status: "editing",
      type: SaveShapeType.bbox,
      shapeId: bbox.id,
      viewRef: bbox.data.view_ref,
      coords,
    };
  };

  const resizeStroke = (currentRect: Konva.Rect) => {
    const viewLayer: Konva.Layer = stage.findOne(`#${bbox.data.view_ref.name}`);
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
      viewRef: bbox.data.view_ref,
      highlighted: "self",
      type: "none",
    };
  };

  const onClick = () => {
    if (bbox.ui.highlighted !== "self") {
      newShape = {
        status: "editing",
        shapeId: bbox.id,
        viewRef: bbox.data.view_ref,
        highlighted: "all",
        type: "none",
      };
    }
    //Note: design-wise, should be better to handle this on a upper level,
    //but in case of interpolated we can't find top_entity with annotation id only
    merge(bbox);
  };

  onDestroy(() => {
    const transformer: Konva.Transformer = stage.findOne("#transformer");
    if (transformer) {
      transformer.nodes([]);
    }
  });

  const handleEditing = async () => {
    //await tick: required to allow redraw of frame when right click "Edit Item" on a different frame
    //not a very elegant solution thought...
    await tick();
    toggleIsEditingBBox(bbox.ui.displayControl?.editing ? "on" : "off", stage, bbox.id);
    if (bbox.ui.displayControl?.editing) {
      const viewLayer: Konva.Layer = stage.findOne(`#${bbox.data.view_ref.name}`);
      if (viewLayer) {
        const currentRect: Konva.Rect = viewLayer.findOne(`#rect${bbox.id}`);
        if (currentRect) {
          currentRect.on("dragmove", (e) =>
            onDragMove(e, stage, bbox.data.view_ref, currentRect, bbox.id),
          );
          currentRect.on("transform", () => resizeStroke(currentRect));
          currentRect.on("transformend dragend", () => {
            updateDimensions(currentRect);
          });
        }
      }
    }
  };

  $: bbox.ui.displayControl?.editing, void handleEditing();
</script>

<Group
  on:dblclick={onDoubleClick}
  on:click={onClick}
  config={{
    listening: selectedTool?.type === ToolType.Pan || selectedTool?.type === ToolType.Fusion,
  }}
>
  <Rect
    config={{
      id: `rect${bbox.id}`,
      x: bbox.data.coords[0] || 0,
      y: bbox.data.coords[1] || 0,
      width: bbox.data.coords[2] || 0,
      height: bbox.data.coords[3] || 0,
      stroke: colorScale(
        bbox.ui.top_entities && bbox.ui.top_entities.length > 0
          ? bbox.ui.top_entities[0].id
          : bbox.data.entity_ref.id,
      ),
      strokeWidth: bbox.ui.strokeFactor * (BBOX_STROKEWIDTH / zoomFactor),
      opacity: bbox.ui.opacity,
      visible: !bbox.ui.displayControl?.hidden,
      draggable: bbox.ui.displayControl?.editing,
    }}
  />
  <LabelTag
    id={bbox.id}
    x={bbox.data.coords[0]}
    y={bbox.data.coords[1]}
    visible={!bbox.ui.displayControl?.hidden}
    {zoomFactor}
    opacity={bbox.ui.opacity}
    tooltip={bbox.ui.tooltip}
    color={colorScale(
      bbox.ui.top_entities && bbox.ui.top_entities.length > 0
        ? bbox.ui.top_entities[0].id
        : bbox.data.entity_ref.id,
    )}
  />
</Group>
