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

  import type { Shape } from "@pixano/core";
  import type { PolygonGroupDetails, PolygonGroupPoint } from "../lib/types/canvas2dTypes";
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
  export let polygonDetails: PolygonGroupDetails;
  export let color: string;
  export let zoomFactor: Record<string, number>;

  let isCurrentPolygonClosed = polygonDetails.status === "created";
  let canEdit = false;
  let polygonShape: {
    simplifiedSvg: string[];
    simplifiedPoints: PolygonGroupPoint[][];
  } = {
    simplifiedSvg: polygonDetails.svg,
    simplifiedPoints: polygonDetails.svg.reduce(
      (acc, val) => [...acc, parseSvgPath(val)],
      [] as PolygonGroupPoint[][],
    ),
  };

  $: canEdit = polygonDetails.editing;

  $: {
    polygonShape.simplifiedPoints = polygonDetails.svg.reduce(
      (acc, val) => [...acc, parseSvgPath(val)],
      [] as PolygonGroupPoint[][],
    );
  }

  $: polygonShape.simplifiedSvg = polygonShape.simplifiedPoints.map((point) =>
    convertPointToSvg(point),
  );

  function handlePolygonPointsDragMove(id: number, i: number) {
    const pos = stage.findOne(`#dot-${polygonDetails.id}-${i}-${id}`).position();
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

    if (polygonDetails.editing) {
      newShape = {
        status: "editing",
        type: "mask",
        shapeId: polygonDetails.id,
        counts,
      };
    }
  }

  const onDoubleClick = () => {
    newShape = {
      status: "editing",
      shapeId: polygonDetails.id,
      isHighlighted: true,
      type: "none",
    };
  };
</script>

<Group
  config={{
    id: "polygon",
    draggable: canEdit,
    visible: polygonDetails.visible,
    opacity: polygonDetails.opacity,
  }}
>
  {#if canEdit}
    <KonvaShape
      config={{
        sceneFunc: (ctx, stage) => sceneFunc(ctx, stage, polygonShape.simplifiedSvg),
        stroke: polygonDetails.status === "created" ? color : "hsl(316deg 60% 29.41%)",
        strokeWidth: 2 / zoomFactor[viewId],
        closed: isCurrentPolygonClosed,
        fill: polygonDetails.status === "created" ? hexToRGBA(color, 0.5) : "#f9f4f773",
      }}
    />
    <PolygonPoints
      {viewId}
      {stage}
      {zoomFactor}
      polygonId={polygonDetails.id}
      points={polygonShape.simplifiedPoints}
      handlePolygonPointsClick={null}
      {handlePolygonPointsDragMove}
      {handlePolygonPointsDragEnd}
    />
  {:else}
    <KonvaShape
      on:dblclick={onDoubleClick}
      config={{
        sceneFunc: (ctx, stage) => sceneFunc(ctx, stage, polygonDetails.svg),
        stroke: polygonDetails.status === "created" ? color : "hsl(316deg 60% 29.41%)",
        strokeWidth: polygonDetails.strokeFactor * (polygonDetails.status === "created" ? 1 : 3),
        closed: isCurrentPolygonClosed,
        fill: polygonDetails.status === "created" ? hexToRGBA(color, 0.5) : "rgb(0,128,0,0.5)",
      }}
    />
  {/if}
</Group>
