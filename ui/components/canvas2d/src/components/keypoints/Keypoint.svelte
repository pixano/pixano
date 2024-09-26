<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { Line } from "svelte-konva";

  import type { KeypointsTemplate, VertexStates } from "@pixano/core";
  import { videoControls } from "../../../../datasetItemWorkspace/src/lib/stores/videoViewerStores";

  import KeyPointCircle from "./KeypointsCircle.svelte";

  export let stage: Konva.Stage;

  export let keypointStructure: KeypointsTemplate;
  export let onPointChange: (vertices: KeypointsTemplate["vertices"]) => void = () => {};
  export let zoomFactor: number;
  export let findPointCoordinate: (point: number, type: "x" | "y") => number = (point) => point;
  export let color: string = "rgba(135, 47, 100)";
  $: edges = keypointStructure.edges;
  $: vertices = keypointStructure.vertices;
  $: keypointsId = keypointStructure.id;

  const onPointDragMove = (pointIndex: number) => {
    if (!keypointStructure.editing) return;
    const pointPosition = stage.findOne(`#keypoint-${keypointsId}-${pointIndex}`).position();
    vertices = vertices.map((point, i) => {
      if (i === pointIndex) {
        return { ...point, x: pointPosition.x, y: pointPosition.y };
      }
      return point;
    });
    onPointChange(vertices);
  };

  const onPointStateChange = (pointIndex: number, value: VertexStates) => {
    vertices = vertices.map((point, i) => {
      if (i === pointIndex) {
        return { ...point, features: { ...point.features, state: value } };
      }
      return point;
    });
    onPointChange(vertices);
  };

  const findVertex = (index: number) => {
    const vertex = vertices[index];
    const vertexX = findPointCoordinate(vertex.x, "x");
    const vertexY = findPointCoordinate(vertex.y, "y");
    return [vertexX, vertexY];
  };

  $: opacity = keypointStructure.highlighted === "none" ? 0.5 : 1;
</script>

<slot />
{#each edges as line}
  <Line
    config={{
      points: [...findVertex(line[0]), ...findVertex(line[1])],
      stroke: color,
      strokeWidth: keypointStructure.highlighted === "self" ? 4 : 2 / zoomFactor,
      opacity,
    }}
  />
{/each}
{#if $videoControls.intervalId == 0}
  {#each vertices as vertex, i}
    <KeyPointCircle
      vertexIndex={i}
      {stage}
      {zoomFactor}
      {vertex}
      {keypointsId}
      {color}
      {opacity}
      {onPointDragMove}
      {findPointCoordinate}
      draggable={keypointStructure.editing}
      {onPointStateChange}
    />
  {/each}
{/if}
