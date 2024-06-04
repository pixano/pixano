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
  import { Group, Line, Rect } from "svelte-konva";

  import type { CreateKeyPointShape, SaveKeyBoxShape } from "@pixano/core";

  import KeyPointCircle from "./KeyPointCircle.svelte";

  export let zoomFactor: Record<string, number>;
  export let newShape: CreateKeyPointShape | SaveKeyBoxShape;
  export let stage: Konva.Stage;
  export let viewId: string;

  let polygonId = "keyPoints";

  const onPointDragMove = (pointIndex: number) => {
    const pointPosition = stage.findOne(`#keyPoint-${polygonId}-${pointIndex}`).position();
    newShape = {
      ...newShape,
      keyPoints: {
        ...newShape.keyPoints,
        vertices: newShape.keyPoints.vertices.map((point, i) => {
          if (i === pointIndex) {
            return { ...point, x: pointPosition.x, y: pointPosition.y };
          }
          return point;
        }),
      },
    };
  };

  const findVertex = (index: number) => {
    const vertex = newShape.keyPoints.vertices[index];
    const vertexX =
      newShape.status === "creating" ? newShape.x + vertex.x * newShape.width : vertex.x;
    const vertexY =
      newShape.status === "creating" ? newShape.y + vertex.y * newShape.height : vertex.y;

    return [vertexX, vertexY];
  };
</script>

{#if newShape.viewId === viewId}
  <Group config={{ id: polygonId, x: 0, y: 0 }}>
    {#if newShape.status === "creating"}
      <Rect
        config={{
          x: newShape.x,
          y: newShape.y,
          width: newShape.width,
          height: newShape.height,
          fill: "rgba(255, 0, 0, 0.4)",
          id: "move-keyPoints-group",
        }}
      />
    {/if}
    {#each newShape.keyPoints.edges as line}
      <Line
        config={{
          points: [...findVertex(line[0]), ...findVertex(line[1])],
          stroke: "#781e60",
          strokeWidth: 2 / zoomFactor[viewId],
        }}
      />
    {/each}
    {#each newShape.keyPoints.vertices as vertex, i}
      <KeyPointCircle
        vertexIndex={i}
        {stage}
        currentZoomFactor={zoomFactor[viewId]}
        {vertex}
        {polygonId}
        {onPointDragMove}
        {newShape}
      />
    {/each}
  </Group>
{/if}
