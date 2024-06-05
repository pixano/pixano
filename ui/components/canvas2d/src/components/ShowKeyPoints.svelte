<script lang="ts">
  import type { KeyPointsTemplate, Shape } from "@pixano/core";

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
  import type Konva from "konva";
  import { Rect } from "svelte-konva";

  import KeyPoints from "./keyPoints/KeyPoints.svelte";

  export let stage: Konva.Stage;
  export let keyPoints: KeyPointsTemplate[] = [];
  export let newShape: Shape;
  export let zoomFactor: number;

  const onKeyPointsChange = (vertices: KeyPointsTemplate["vertices"], id: string) => {
    newShape = {
      status: "editing",
      type: "keyPoint",
      vertices,
      shapeId: id,
    };
  };

  const findRectBoundaries = (vertices: KeyPointsTemplate["vertices"]) => {
    const x = Math.min(...vertices.map((point) => point.x));
    const y = Math.min(...vertices.map((point) => point.y));
    const width = Math.max(...vertices.map((point) => point.x)) - x;
    const height = Math.max(...vertices.map((point) => point.y)) - y;
    return { x, y, width, height };
  };
</script>

{#if keyPoints}
  {#each keyPoints as keyPointStructure}
    <KeyPoints
      onPointChange={(vertices) => onKeyPointsChange(vertices, keyPointStructure.id)}
      {stage}
      {keyPointStructure}
      {zoomFactor}
    >
      {#if keyPointStructure.editing}
        <Rect
          config={{
            x: findRectBoundaries(keyPointStructure.vertices).x - 10 / zoomFactor,
            y: findRectBoundaries(keyPointStructure.vertices).y - 10 / zoomFactor,
            width: findRectBoundaries(keyPointStructure.vertices).width + 20 / zoomFactor,
            height: findRectBoundaries(keyPointStructure.vertices).height + 20 / zoomFactor,
            fill: "rgba(135, 47, 100, 0.1)",
            stroke: "rgba(135, 47, 100, 0.8)",
            id: "move-keyPoints-group",
            listening: false,
          }}
        />
      {/if}
    </KeyPoints>
  {/each}
{/if}
