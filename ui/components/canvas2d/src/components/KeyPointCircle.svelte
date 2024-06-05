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

  import { Circle } from "svelte-konva";

  import type { Vertex } from "@pixano/core";

  import type Konva from "konva";
  import LabelTag from "./LabelTag.svelte";

  export let stage: Konva.Stage;
  export let currentZoomFactor: number;
  export let vertex: Vertex;
  export let keyPointsId: string;
  export let onPointDragMove: (pointId: number) => void;
  export let vertexIndex: number;
  export let findPointCoordinate: (point: number, type: "x" | "y") => number = (point) => point;
  export let draggable: boolean = false;

  let showLabel = false;

  const scaleCircleRadius = (id: number, scale: number) => {
    const point: Konva.Circle = stage.findOne(`#keyPoint-${keyPointsId}-${id}`);

    point.scaleX(scale);
    point.scaleY(scale);
  };

  const onMouseOver = () => {
    if (!draggable) return;
    scaleCircleRadius(vertexIndex, 2);
    showLabel = true;
  };

  const onMouseLeave = () => {
    scaleCircleRadius(vertexIndex, 1);
    showLabel = false;
  };

  $: x = findPointCoordinate(vertex.x, "x");
  $: y = findPointCoordinate(vertex.y, "y");
</script>

<Circle
  config={{
    x,
    y,
    radius: 4 / currentZoomFactor,
    fill: "rgb(0,128,0)",
    stroke: "white",
    strokeWidth: 1 / currentZoomFactor,
    id: `keyPoint-${keyPointsId}-${vertexIndex}`,
    draggable,
  }}
  on:dragmove={() => onPointDragMove(vertexIndex)}
  on:mouseover={onMouseOver}
  on:mouseleave={onMouseLeave}
/>
{#if vertex.features}
  <LabelTag
    x={x + 16 / currentZoomFactor}
    {y}
    id={`${vertexIndex}`}
    visible={showLabel}
    zoomFactor={currentZoomFactor}
    color="rgb(0,128,0)"
    tooltip={vertex.features.join(", ")}
  />
{/if}
