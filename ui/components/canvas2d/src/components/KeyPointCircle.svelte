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

  import type { BasePoint, CreateKeyPointShape, SaveKeyBoxShape } from "@pixano/core";

  import type Konva from "konva";
  import LabelTag from "./LabelTag.svelte";

  export let stage: Konva.Stage;
  export let currentZoomFactor: number;
  export let vertex: BasePoint;
  export let polygonId: string;
  export let onPointDragMove: (pointId: number) => void;
  export let vertexIndex: number;
  export let newShape: CreateKeyPointShape | SaveKeyBoxShape;

  let showLabel = false;

  const scaleCircleRadius = (id: number, scale: number) => {
    const point: Konva.Circle = stage.findOne(`#keyPoint-${polygonId}-${id}`);

    point.scaleX(scale);
    point.scaleY(scale);
  };

  const onMouseOver = () => {
    scaleCircleRadius(vertexIndex, 2);
    showLabel = true;
  };

  const onMouseLeave = () => {
    scaleCircleRadius(vertexIndex, 1);
    showLabel = false;
  };

  $: x = newShape.status === "creating" ? newShape.x + vertex.x * newShape.width : vertex.x;
  $: y = newShape.status === "creating" ? newShape.y + vertex.y * newShape.height : vertex.y;

  $: console.log({ x, y, vertex });
</script>

<Circle
  config={{
    x,
    y,
    radius: 4 / currentZoomFactor,
    fill: "rgb(0,128,0)",
    stroke: "white",
    strokeWidth: 1 / currentZoomFactor,
    id: `keyPoint-${polygonId}-${vertexIndex}`,
    draggable: true,
  }}
  on:dragmove={() => onPointDragMove(vertexIndex)}
  on:mouseover={onMouseOver}
  on:mouseleave={onMouseLeave}
/>
<LabelTag
  x={x + 16 / currentZoomFactor}
  {y}
  id={`${vertexIndex}`}
  visible={showLabel}
  zoomFactor={currentZoomFactor}
  color="rgb(0,128,0)"
  tooltip={vertex.features?.join(", ")}
/>
