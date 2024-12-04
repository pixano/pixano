<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { Group, Shape as KonvaShape } from "svelte-konva";

  import type { Mask, SelectionTool, Shape, Reference } from "@pixano/core";
  import type { PolygonGroupPoint, PolygonShape } from "../lib/types/textCanvas2dTypes";
  import {
    sceneFunc,
    hexToRGBA,
    convertPointToSvg,
    parseSvgPath,
    runLengthEncode,
  } from "../api/maskApi";
  import PolygonPoints from "./PolygonPoints.svelte";

  // Exports
  export let viewRef: Reference;
  export let newShape: Shape;
  export let stage: Konva.Stage;
  export let currentImage: HTMLImageElement;
  export let mask: Mask;
  export let color: string;
  export let zoomFactor: Record<string, number>;
  export let selectedTool: SelectionTool;

  let canEdit = false;
  let polygonShape: PolygonShape = {
    simplifiedSvg: mask.ui.svg,
    simplifiedPoints: mask.ui.svg.reduce(
      (acc, val) => [...acc, parseSvgPath(val)],
      [] as PolygonGroupPoint[][],
    ),
  };

  $: canEdit = mask.ui.displayControl?.editing;

  $: {
    polygonShape.simplifiedPoints = mask.ui.svg.reduce(
      (acc, val) => [...acc, parseSvgPath(val)],
      [] as PolygonGroupPoint[][],
    );
  }

  $: polygonShape.simplifiedSvg = polygonShape.simplifiedPoints.map((point) =>
    convertPointToSvg(point),
  );

  const handlePolygonPointsDragMove = (id: number, i: number) => {
    const pos = stage.findOne(`#dot-${mask.id}-${i}-${id}`).position();
    const newSimplifiedPoints = polygonShape.simplifiedPoints.map((points, pi) =>
      pi === i
        ? points.map((point) => (point.id === id ? { ...point, x: pos.x, y: pos.y } : point))
        : points,
    );
    polygonShape.simplifiedPoints = newSimplifiedPoints;
  };

  const handlePolygonPointsDragEnd = (svg?: string[]) => {
    const counts = runLengthEncode(
      svg || polygonShape.simplifiedSvg,
      currentImage.width,
      currentImage.height,
    );

    if (mask.ui.displayControl.editing) {
      newShape = {
        status: "editing",
        type: "mask",
        viewRef,
        shapeId: mask.id,
        counts,
      };
    }
  };

  const handlePolygonDragEnd = (target: Konva.Group) => {
    if (target.id() !== `polygon-${mask.id}`) return;
    const moveX = target.x();
    const moveY = target.y();
    const newSimplifiedPoints = polygonShape.simplifiedPoints.map((points) =>
      points.map((point) => ({ ...point, x: point.x + moveX, y: point.y + moveY })),
    );
    const currentPolygon = stage.findOne(`#polygon-${mask.id}`);
    currentPolygon.position({ x: 0, y: 0 });
    polygonShape.simplifiedPoints = newSimplifiedPoints;
    const svg = polygonShape.simplifiedPoints.map((point) => convertPointToSvg(point));
    handlePolygonPointsDragEnd(svg);
  };

  const onDoubleClick = () => {
    newShape = {
      status: "editing",
      shapeId: mask.id,
      viewRef,
      highlighted: "self",
      type: "none",
    };
  };

  const onClick = () => {
    if (mask.ui.highlighted !== "self") {
      newShape = {
        status: "editing",
        shapeId: mask.id,
        viewRef,
        highlighted: "all",
        type: "none",
      };
    }
  };
</script>

<Group
  on:dragend={(e) => handlePolygonDragEnd(e.detail.target)}
  config={{
    id: `polygon-${mask.id}`,
    draggable: canEdit,
    visible: !mask.ui.displayControl?.hidden,
    opacity: mask.ui.opacity,
    listening: selectedTool.type === "PAN",
  }}
>
  {#if canEdit}
    <KonvaShape
      config={{
        sceneFunc: (ctx, stage) => sceneFunc(ctx, stage, polygonShape.simplifiedSvg),
        stroke: color,
        strokeWidth: 2 / zoomFactor[viewRef.name],
        closed: true,
        fill: hexToRGBA(color, 0.5),
      }}
    />
    <PolygonPoints
      {viewRef}
      {stage}
      {zoomFactor}
      polygonId={mask.id}
      points={polygonShape.simplifiedPoints}
      handlePolygonPointsClick={null}
      {handlePolygonPointsDragMove}
      {handlePolygonPointsDragEnd}
    />
  {:else}
    <KonvaShape
      on:dblclick={onDoubleClick}
      on:click={onClick}
      config={{
        sceneFunc: (ctx, stage) => sceneFunc(ctx, stage, mask.ui.svg),
        stroke: color,
        strokeWidth: mask.ui.strokeFactor,
        closed: true,
        fill: hexToRGBA(color, 0.5),
        id: mask.id,
      }}
    />
  {/if}
</Group>
