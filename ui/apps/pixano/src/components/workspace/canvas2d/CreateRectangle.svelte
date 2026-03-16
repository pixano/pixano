<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type Konva from "konva";
  import { Group, Rect, Transformer } from "svelte-konva";

  import { DRAFT_LINE_COLOR, DRAFT_RECT_FILL_COLOR, INPUTRECT_STROKEWIDTH } from "./konvaConstants";
  import LabelTag from "./LabelTag.svelte";
  import type { Reference } from "$lib/types/dataset";
  import type { BoundingBox, Point2D } from "$lib/types/geometry";
  import type { CreateRectangleShape, SaveRectangleShape } from "$lib/types/shapeTypes";

  interface Props {
    zoomFactor: number;
    newShape: CreateRectangleShape | SaveRectangleShape;
    viewRef: Reference;
    editable?: boolean;
    onTransformEnd?: (geometry: BoundingBox) => void;
    onDragEnd?: (position: Point2D) => void;
  }

  let {
    zoomFactor,
    newShape,
    viewRef,
    editable = false,
    onTransformEnd,
    onDragEnd,
  }: Props = $props();

  let rectComponent: { node: Konva.Rect } | undefined = $state();
  let trComponent: { node: Konva.Transformer } | undefined = $state();

  // Attach transformer to rect when editable
  $effect(() => {
    const tr = trComponent?.node;
    const rect = rectComponent?.node;
    if (editable && tr && rect) {
      tr.nodes([rect]);
      tr.getLayer()?.batchDraw();
    } else if (tr) {
      tr.nodes([]);
    }
  });

  function handleTransformEnd(e: Konva.KonvaEventObject<Event>) {
    const rect = e.target as Konva.Rect;
    const finalWidth = rect.width() * rect.scaleX();
    const finalHeight = rect.height() * rect.scaleY();
    rect.setAttrs({ width: finalWidth, height: finalHeight, scaleX: 1, scaleY: 1 });
    onTransformEnd?.({ x: rect.x(), y: rect.y(), width: finalWidth, height: finalHeight });
  }

  function handleDragEnd(e: Konva.KonvaEventObject<DragEvent>) {
    const rect = e.target as Konva.Rect;
    onDragEnd?.({ x: rect.x(), y: rect.y() });
  }

  let x = $derived(newShape.status === "creating" ? newShape.x : newShape.attrs.x);
  let y = $derived(newShape.status === "creating" ? newShape.y : newShape.attrs.y);
  let width = $derived(newShape.status === "creating" ? newShape.width : newShape.attrs.width);
  let height = $derived(newShape.status === "creating" ? newShape.height : newShape.attrs.height);
</script>

{#if newShape.viewRef.name === viewRef.name}
  <Group id="drag-rect-group">
    <Rect
      bind:this={rectComponent}
      id="drag-rect"
      {x}
      {y}
      {width}
      {height}
      stroke={DRAFT_LINE_COLOR}
      fill={DRAFT_RECT_FILL_COLOR}
      strokeScaleEnabled={false}
      perfectDrawEnabled={false}
      shadowForStrokeEnabled={false}
      listening={editable}
      draggable={editable}
      ondragend={handleDragEnd}
      ontransformend={handleTransformEnd}
    />
    {#if editable}
      <Transformer bind:this={trComponent} rotateEnabled={false} keepRatio={false} />
    {/if}
    {#if x && y}
      <LabelTag
        id="drag-rect-tag"
        {x}
        {y}
        {zoomFactor}
        tooltip={`${Math.round(Math.abs(width))}px x ${Math.round(Math.abs(height))}px`}
        color="white"
      />
    {/if}
  </Group>
{/if}
