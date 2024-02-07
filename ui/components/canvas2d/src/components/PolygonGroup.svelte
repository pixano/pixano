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
  import { Group, Shape as KonvaShape } from "svelte-konva";

  import type { Mask, Shape } from "@pixano/core";
  import type { PolygonGroupPoint, PolygonShape } from "../lib/types/canvas2dTypes";
  import {
    sceneFunc,
    hexToRGBA,
    convertPointToSvg,
    parseSvgPath,
    runLengthEncode,
  } from "../api/maskApi";
  import PolygonPoints from "./PolygonPoints.svelte";

  // Exports
  export let viewId: string;
  export let newShape: Shape;
  export let stage: Konva.Stage;
  export let images: Record<string, HTMLImageElement> = {};
  export let mask: Mask;
  export let color: string;
  export let zoomFactor: Record<string, number>;

  let canEdit = false;
  let polygonShape: PolygonShape = {
    simplifiedSvg: mask.svg,
    simplifiedPoints: mask.svg.reduce(
      (acc, val) => [...acc, parseSvgPath(val)],
      [] as PolygonGroupPoint[][],
    ),
  };

  $: canEdit = mask.editing;

  $: {
    polygonShape.simplifiedPoints = mask.svg.reduce(
      (acc, val) => [...acc, parseSvgPath(val)],
      [] as PolygonGroupPoint[][],
    );
  }

  $: polygonShape.simplifiedSvg = polygonShape.simplifiedPoints.map((point) =>
    convertPointToSvg(point),
  );

  function handlePolygonPointsDragMove(id: number, i: number) {
    const pos = stage.findOne(`#dot-${mask.id}-${i}-${id}`).position();
    const newSimplifiedPoints = polygonShape.simplifiedPoints.map((points, pi) =>
      pi === i
        ? points.map((point) => (point.id === id ? { ...point, x: pos.x, y: pos.y } : point))
        : points,
    );
    polygonShape.simplifiedPoints = newSimplifiedPoints;
  }

  function handlePolygonPointsDragEnd() {
    const counts = runLengthEncode(
      polygonShape.simplifiedSvg,
      images[viewId].width,
      images[viewId].height,
    );
    console.log("end");

    if (mask.editing) {
      newShape = {
        status: "editing",
        type: "mask",
        shapeId: mask.id,
        counts,
      };
    }
  }

  const onDoubleClick = () => {
    newShape = {
      status: "editing",
      shapeId: mask.id,
      highlighted: "self",
      type: "none",
    };
  };

  const onClick = () => {
    if (mask.highlighted !== "self") {
      newShape = {
        status: "editing",
        shapeId: mask.id,
        highlighted: "all",
        type: "none",
      };
    }
  };
</script>

<Group
  on:dragend={handlePolygonPointsDragEnd}
  config={{
    id: "polygon",
    draggable: canEdit,
    visible: mask.visible,
    opacity: mask.opacity,
  }}
>
  {#if canEdit}
    <KonvaShape
      config={{
        sceneFunc: (ctx, stage) => sceneFunc(ctx, stage, polygonShape.simplifiedSvg),
        stroke: color,
        strokeWidth: 2 / zoomFactor[viewId],
        closed: true,
        fill: hexToRGBA(color, 0.5),
      }}
    />
    <PolygonPoints
      {viewId}
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
        sceneFunc: (ctx, stage) => sceneFunc(ctx, stage, mask.svg),
        stroke: color,
        strokeWidth: mask.strokeFactor,
        closed: true,
        fill: hexToRGBA(color, 0.5),
        id: mask.id,
      }}
    />
  {/if}
</Group>
