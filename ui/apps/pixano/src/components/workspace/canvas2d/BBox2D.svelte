<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type Konva from "konva";
  import { Group, Rect, Transformer } from "svelte-konva";

  import { clampRectToImage, getRectNormalizedCoords } from "./canvasGeometry";
  import { BBOX_STROKEWIDTH } from "./konvaConstants";
  import LabelTag from "./LabelTag.svelte";
  import { NEUTRAL_ENTITY_COLOR } from "$lib/constants/workspaceConstants";
  import type { BBox } from "$lib/types/dataset";
  import { ShapeType, type Shape } from "$lib/types/shapeTypes";

  interface Props {
    bbox: BBox;
    colorScale: (id: string) => string;
    zoomFactor: number;
    listening: boolean;
    imageWidth?: number;
    imageHeight?: number;
    merge?: (ann: { id: string }) => void;
    onNewShapeChange?: (shape: Shape) => void;
  }

  let {
    bbox,
    colorScale,
    zoomFactor,
    listening,
    imageWidth = 0,
    imageHeight = 0,
    merge,
    onNewShapeChange,
  }: Props = $props();

  let rectComponent: { node: Konva.Rect } | undefined = $state();
  let trComponent: { node: Konva.Transformer } | undefined = $state();

  let editing = $derived(bbox.ui.displayControl.editing);
  let color = $derived.by(() => {
    if (bbox.ui.displayControl.highlighted === "none") return NEUTRAL_ENTITY_COLOR;
    return colorScale(
      (bbox.ui.top_entities ?? []).length > 0
        ? (bbox.ui.top_entities ?? [])[0].id
        : bbox.data.entity_id,
    );
  });

  // Attach transformer to rect when editing
  $effect(() => {
    const tr = trComponent?.node;
    const rect = rectComponent?.node;
    if (editing && tr && rect) {
      tr.nodes([rect]);
      tr.getLayer()?.batchDraw();
    } else if (tr) {
      tr.nodes([]);
    }
  });

  function handleClick() {
    if (bbox.ui.displayControl.highlighted !== "self") {
      onNewShapeChange?.({
        status: "editing",
        shapeId: bbox.id,
        top_entity_id: (bbox.ui.top_entities ?? [])[0]?.id,
        viewRef: { name: bbox.data.view_name, id: bbox.data.frame_id },
        highlighted: "self",
        type: ShapeType.none,
      });
    }
    merge?.(bbox);
  }

  function emitCoords(rect: Konva.Rect) {
    if (!imageWidth || !imageHeight) return;
    const coords = getRectNormalizedCoords(
      rect.x(),
      rect.y(),
      rect.width() * rect.scaleX(),
      rect.height() * rect.scaleY(),
      imageWidth,
      imageHeight,
    );
    onNewShapeChange?.({
      status: "editing",
      type: ShapeType.bbox,
      shapeId: bbox.id,
      viewRef: { name: bbox.data.view_name, id: bbox.data.frame_id },
      coords: [...coords],
    });
  }

  function handleDragMove(e: Konva.KonvaEventObject<DragEvent>) {
    const rect = e.target as Konva.Rect;
    if (!imageWidth || !imageHeight) return;
    const clamped = clampRectToImage(
      rect.x(),
      rect.y(),
      rect.width(),
      rect.height(),
      imageWidth,
      imageHeight,
    );
    rect.x(clamped.x);
    rect.y(clamped.y);
  }

  function handleDragEnd(e: Konva.KonvaEventObject<DragEvent>) {
    emitCoords(e.target as Konva.Rect);
  }

  function handleTransform(e: Konva.KonvaEventObject<Event>) {
    const rect = e.target as Konva.Rect;
    // Normalize scale into width/height
    rect.setAttrs({
      width: rect.width() * rect.scaleX(),
      height: rect.height() * rect.scaleY(),
      scaleX: 1,
      scaleY: 1,
    });
  }

  function handleTransformEnd(e: Konva.KonvaEventObject<Event>) {
    emitCoords(e.target as Konva.Rect);
  }
</script>

<Group {listening} onclick={handleClick}>
  <Rect
    bind:this={rectComponent}
    id={`rect${bbox.id}`}
    x={bbox.data.coords[0]}
    y={bbox.data.coords[1]}
    width={bbox.data.coords[2]}
    height={bbox.data.coords[3]}
    stroke={color}
    strokeScaleEnabled={false}
    perfectDrawEnabled={false}
    shadowForStrokeEnabled={false}
    opacity={bbox.ui.opacity ?? 1}
    visible={!bbox.ui.displayControl.hidden}
    draggable={editing}
    ondragmove={handleDragMove}
    ondragend={handleDragEnd}
    ontransform={handleTransform}
    ontransformend={handleTransformEnd}
  />
  {#if editing}
    <Transformer bind:this={trComponent} rotateEnabled={false} />
  {/if}
  <LabelTag
    id={bbox.id}
    x={bbox.data.coords[0]}
    y={bbox.data.coords[1]}
    visible={!bbox.ui.displayControl.hidden}
    {zoomFactor}
    opacity={bbox.ui.opacity ?? 1}
    tooltip={bbox.ui.tooltip ?? ""}
    {color}
  />
</Group>
