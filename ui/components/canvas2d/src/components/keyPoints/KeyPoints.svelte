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
  import { Line } from "svelte-konva";

  import type { KeyPointsTemplate } from "@pixano/core";

  import KeyPointCircle from "./KeyPointCircle.svelte";

  export let stage: Konva.Stage;

  export let keyPointStructure: KeyPointsTemplate;
  export let onPointChange: (vertices: KeyPointsTemplate["vertices"]) => void = () => {};
  export let zoomFactor: number;
  export let findPointCoordinate: (point: number, type: "x" | "y") => number = (point) => point;

  $: edges = keyPointStructure.edges;
  $: vertices = keyPointStructure.vertices;
  $: keyPointsId = keyPointStructure.id;

  const onPointDragMove = (pointIndex: number) => {
    if (!keyPointStructure.editing) return;
    const pointPosition = stage.findOne(`#keyPoint-${keyPointsId}-${pointIndex}`).position();
    vertices = vertices.map((point, i) => {
      if (i === pointIndex) {
        return { ...point, x: pointPosition.x, y: pointPosition.y };
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
</script>

<slot />
{#each edges as line}
  <Line
    config={{
      points: [...findVertex(line[0]), ...findVertex(line[1])],
      stroke: "#781e60",
      strokeWidth: 2 / zoomFactor,
    }}
  />
{/each}
{#each vertices as vertex, i}
  <KeyPointCircle
    vertexIndex={i}
    {stage}
    {zoomFactor}
    {vertex}
    {keyPointsId}
    {onPointDragMove}
    {findPointCoordinate}
    draggable={keyPointStructure.editing}
  />
{/each}
